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
        return True
                
    def _credentials(self):
        """
        """
        logger.debug('Setting up credentials.')
        if os.path.exists(self.configuration['Server']['token_file']):
            logger.debug(f"Retrieving credentials from {self.configuration['Server']['token_file']=}")
            self.creds = Credentials.from_authorized_user_file(self.configuration['Server']['token_file'])
        if not self.creds or not self.creds.valid:
            logger.debug(f"Credentials are not existing/valid")
            if self.creds and self.creds.expired and self.creds.refresh_token:
                logger.debug(f"Credential refresh request called.")
                self.creds.refresh(Request())
            else:
                logger.debug(f"Setting up flow.")
                flow = InstalledAppFlow.from_client_secrets_file(self.configuration['Server']['credentials_file'], SCOPES)
                self.creds = flow.run_local_server(port=0)
            with open(self.configuration['Server']['token_file'], 'w') as token:
                token.write(self.creds.to_json())
        return self.creds

    def configure(self):
        """
        """
        logger.info("Configuring it all together.")
        self._process_detail_file()
        self._credentials()
        logger.debug('Created credentials - building service.')
        self.service = build('gmail', 'v1', credentials = self.creds)

    def read_email(self):
        logger.info('Getting list of emails in UNREAD state')
        try:
            # Call the Gmail API
            results = self.service.users().messages().list(userId='me', labelIds= ['UNREAD']).execute()
            messages = results.get('messages', [])

            for message in messages:
                msg = self.service.users().messages().get(userId='me', id=message['id']).execute()
                for thing in msg['payload']['parts']:
                    print(base64.b64decode(thing['body']['data']))
                
                # for k in msg.items():
                #     print(k[0])
                self.service.users().messages().modify(userId='me',
                                                       id=message['id'],
                                                       body={'removeLabelIds': ['UNREAD']}).execute()

        except HttpError as error:
            # TODO(developer) - Handle errors from gmail API.
            print(f'An error occurred: {error}')        

    def send_message_internal(self, service, user_id, message):
        """
        """
        try:
            message = (self.service.users().messages().send(userId=user_id, body=message).execute())
            print('Message Id: %s' % message['id'])
            return message
        except errors.HttpError as error:
            print('An error occurred: %s' % error)
            return "Error"
        return "OK"

    def create_message_html(self, sender, to, subject, msg_html, msg_plain):
        """
        """
        logger.info(f'Creating {sender=} {to=} {subject=}')
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = sender
        msg['To'] = to
        msg.attach(MIMEText(msg_plain, 'plain'))
        msg.attach(MIMEText(msg_html, 'html'))
        return {'raw': base64.urlsafe_b64encode(msg.as_bytes()).decode()}

    def create_message_with_attachment(
            self, sender, to, subject, msg_html, msg_plain, attachment_file):
        """Create a message for an email.

        Args:
          sender: Email address of the sender.
          to: Email address of the receiver.
          subject: The subject of the email message.
          msg_html: Html message to be sent
          msg_plain: Alternative plain text message for older email clients          
          attachment_file: The path to the file to be attached.

        Returns:
          An object containing a base64url encoded email object.
        """
        message = MIMEMultipart('mixed')
        message['to'] = to
        message['from'] = sender
        message['subject'] = subject

        message_a = MIMEMultipart('alternative')
        message_r = MIMEMultipart('related')

        message_r.attach(MIMEText(msg_html, 'html'))
        message_a.attach(MIMEText(msg_plain, 'plain'))
        message_a.attach(message_r)

        message.attach(message_a)

        print("create_message_with_attachment: file: %s" % attachment_file)
        content_type, encoding = mimetypes.guess_type(attachment_file)

        if content_type is None or encoding is not None:
            content_type = 'application/octet-stream'
        main_type, sub_type = content_type.split('/', 1)
        if main_type == 'text':
            fp = open(attachment_file, 'rb')
            msg = MIMEText(fp.read(), _subtype=sub_type)
            fp.close()
        elif main_type == 'image':
            fp = open(attachment_file, 'rb')
            msg = MIMEImage(fp.read(), _subtype=sub_type)
            fp.close()
        elif main_type == 'audio':
            fp = open(attachment_file, 'rb')
            msg = MIMEAudio(fp.read(), _subtype=sub_type)
            fp.close()
        else:
            fp = open(attachment_file, 'rb')
            msg = MIMEBase(main_type, sub_type)
            msg.set_payload(fp.read())
            fp.close()
        filename = os.path.basename(attachment_file)
        msg.add_header('Content-Disposition', 'attachment', filename=filename)
        message.attach(msg)

        return {'raw': base64.urlsafe_b64encode(message.as_bytes()).decode()}

    
    def send_message(self, sender, to, subject, msg_html, msg_plain, attachment_file=None):
        """
        """
        logger.info("About to send message.")
        logger.info("Build http...")
        if attachment_file:
            logger.debug('Attachments')
            message1 = self.create_message_with_attachment(sender, to, subject, msg_html, msg_plain, attachment_file)
        else:
            logger.debug('No attachments!')
            message1 = self.create_message_html(sender, to, subject, msg_html, msg_plain)
            result = self.send_message_internal(self.service, "me", message1)
        return result
    

def main():
    x = EmailHandler('../templates/test.ini')
    x.configure()
    x.read_email()


if __name__ == "__main__":
    main()
