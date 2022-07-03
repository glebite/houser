"""email_handler.py

A big chunk has been lifted from:
https://stackoverflow.com/questions/37201250/sending-email-via-gmail-python
"""
from __future__ import print_function

import os.path
import configparser

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import httplib2
import os
import sys
import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from apiclient import errors, discovery
import mimetypes
from email.mime.image import MIMEImage
from email.mime.audio import MIMEAudio
from email.mime.base import MIMEBase

from base_logger import logger


SCOPES = ['https://www.googleapis.com/auth/gmail.readonly',
          'https://www.googleapis.com/auth/gmail.modify']


class EmailHandler:
    """EmailHandler
    """
    def __init__(self, detail_file):
        """__init__
        """
        logger.info(f'Instantiating {self=}')
        self.service = None
        self.creds = None
        self.configuration = None
        self.detail_file = detail_file

    def _process_detail_file(self):
        """_process_detail_file
        """
        logger.debug(f'Processing {self.detail_file=}')
        if not os.path.exists(self.detail_file):
            logger.error(f'Could not find: {self.detail_file=}')
            sys.exit(-1)
        else:
            logger.debug('Evaluating and loading the configuration parameters')
            self.configuration = configparser.ConfigParser()
            try:
                self.configuration.read(self.detail_file)
            except (configparser.Error, IOError, OSError) as err:
                logger.error(f'Failing due to: {err=}')
                sys.exit(1)
                
    def _credentials(self):
        """
        """
        logger.debug('Setting up credentials.')
        if os.path.exists(self.configuration['Server']['token_file']):
            self.creds = Credentials.from_authorized_user_file(self.configuration['Server']['token_file'])
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(self.configuration['Server']['credentials_file'], SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open(self.configuration['Server']['token_file'], 'w') as token:
                token.write(self.creds.to_json())

    def configure(self):
        """
        """
        logger.info("Configuring it all together.")
        self._process_detail_file()
        self._credentials()
        self.service = build('gmail', 'v1', credentials = self.creds)


    def read_email(self):
        """ IOU: refactoring...
        """
        logger.info('Getting list of emails in UNREAD state')
        try:
            # Call the Gmail API
            results = self.service.users().messages().list(userId='me', labelIds= ['UNREAD']).execute()
            messages = results.get('messages', [])

            for message in messages:
                msg = self.service.users().messages().get(userId='me', id=message['id']).execute()
                print(dir(msg))
                for k in msg.items():
                    print(k)
                self.service.users().messages().modify(userId='me', id=message['id'], body={'removeLabelIds': ['UNREAD']}).execute()

        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            print(f'An error occurred: {error}')        

    def send_mail(self,
                  to_address,
                  subject,
                  body,
                  attachments):
        """send_mail
        """
        pass

    def SendMessageInternal(service, user_id, message):
        """
        """
        try:
            message = (service.users().messages().send(userId=user_id, body=message).execute())
            print('Message Id: %s' % message['id'])
            return message
        except errors.HttpError as error:
            print('An error occurred: %s' % error)
            return "Error"
        return "OK"

    def CreateMessageHtml(sender, to, subject, msgHtml, msgPlain):
        """
        """
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to
        msg.attach(MIMEText(msgPlain, 'plain'))
        msg.attach(MIMEText(msgHtml, 'html'))
        return {'raw': base64.urlsafe_b64encode(msg.as_bytes()).decode()}

    def createMessageWithAttachment(
        sender, to, subject, msgHtml, msgPlain, attachmentFile):
        """Create a message for an email.

        Args:
          sender: Email address of the sender.
          to: Email address of the receiver.
          subject: The subject of the email message.
          msgHtml: Html message to be sent
          msgPlain: Alternative plain text message for older email clients          
          attachmentFile: The path to the file to be attached.

        Returns:
          An object containing a base64url encoded email object.
        """
        message = MIMEMultipart('mixed')
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject

        messageA = MIMEMultipart('alternative')
        messageR = MIMEMultipart('related')

        messageR.attach(MIMEText(msgHtml, 'html'))
        messageA.attach(MIMEText(msgPlain, 'plain'))
        messageA.attach(messageR)

        message.attach(messageA)

        print("create_message_with_attachment: file: %s" % attachmentFile)
        content_type, encoding = mimetypes.guess_type(attachmentFile)

        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'
        main_type, sub_type = content_type.split('/', 1)
        if main_type == 'text':
            fp = open(attachmentFile, 'rb')
            msg = MIMEText(fp.read(), _subtype=sub_type)
            fp.close()
        elif main_type == 'image':
            fp = open(attachmentFile, 'rb')
            msg = MIMEImage(fp.read(), _subtype=sub_type)
            fp.close()
        elif main_type == 'audio':
            fp = open(attachmentFile, 'rb')
            msg = MIMEAudio(fp.read(), _subtype=sub_type)
            fp.close()
        else:
            fp = open(attachmentFile, 'rb')
            msg = MIMEBase(main_type, sub_type)
            msg.set_payload(fp.read())
            fp.close()
        filename = os.path.basename(attachmentFile)
        msg.add_header('Content-Disposition', 'attachment', filename=filename)
        message.attach(msg)

        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}


    def SendMessage(self, sender, to, subject, msgHtml, msgPlain, attachmentFile=None):
        """
        """
        http = self.creds.authorize(httplib2.Http())
        service = discovery.build('gmail', 'v1', http=http)
        if attachmentFile:
            message1 = self.createMessageWithAttachment(sender, to, subject, msgHtml, msgPlain, attachmentFile)
        else: 
            message1 = self.CreateMessageHtml(sender, to, subject, msgHtml, msgPlain)
            result = self.SendMessageInternal(service, "me", message1)
        return result
    

def main():
    x = EmailHandler('../templates/test.ini')
    x.configure()
    x.read_email()


if __name__ == "__main__":
    main()
