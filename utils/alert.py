from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

from builtins import str
from past.builtins import basestring

import importlib
import logging
import os
import smtplib
import urllib2, json
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from email.utils import formatdate

from airflow import configuration
from airflow.exceptions import AirflowConfigException


class Email():
    def send(self, to, subject, html_content, files=None, dryrun=False, cc=None, bcc=None, mime_subtype='mixed'):
        """
        Send email using backend specified in EMAIL_BACKEND.
        """
        try:
            path, attr = configuration.get('email', 'EMAIL_BACKEND').rsplit('.', 1)
            module = importlib.import_module(path)
            backend = getattr(module, attr)
            return backend(to, subject, html_content, files=files, dryrun=dryrun, cc=cc, bcc=bcc, mime_subtype=mime_subtype)
        except Exception :
            logging.error('Failed to send email to: ' + str(to))

    def get_email_address_list(self, address_string):
        if isinstance(address_string, basestring):
            if ',' in address_string:
                address_string = address_string.split(',')
            elif ';' in address_string:
                address_string = address_string.split(';')
            else:
                address_string = [address_string]

        return address_string

    def send_email_smtp(self, to, subject, html_content, files=None, dryrun=False, cc=None, bcc=None,
                        mime_subtype='mixed'):
        """
        Send an email with html content

        >>> send_email('test@example.com', 'foo', '<b>Foo</b> bar', ['/dev/null'], dryrun=True)
        """
        SMTP_MAIL_FROM = configuration.get('smtp', 'SMTP_MAIL_FROM')

        to = self.get_email_address_list(to)

        msg = MIMEMultipart(mime_subtype)
        msg['Subject'] = subject
        msg['From'] = SMTP_MAIL_FROM
        msg['To'] = ", ".join(to)
        recipients = to
        if cc:
            cc = self.get_email_address_list(cc)
            msg['CC'] = ", ".join(cc)
            recipients = recipients + cc

        if bcc:
            # don't add bcc in header
            bcc = self.get_email_address_list(bcc)
            recipients = recipients + bcc

        msg['Date'] = formatdate(localtime=True)
        mime_text = MIMEText(html_content, 'html')
        msg.attach(mime_text)

        for fname in files or []:
            basename = os.path.basename(fname)
            with open(fname, "rb") as f:
                part = MIMEApplication(
                    f.read(),
                    Name=basename
                )
                part['Content-Disposition'] = 'attachment; filename="%s"' % basename
                msg.attach(part)

        self.send_MIME_email(SMTP_MAIL_FROM, recipients, msg, dryrun)

    def send_MIME_email(self, e_from, e_to, mime_msg, dryrun=False):
        SMTP_HOST = configuration.get('smtp', 'SMTP_HOST')
        SMTP_PORT = configuration.getint('smtp', 'SMTP_PORT')
        SMTP_STARTTLS = configuration.getboolean('smtp', 'SMTP_STARTTLS')
        SMTP_SSL = configuration.getboolean('smtp', 'SMTP_SSL')
        SMTP_USER = None
        SMTP_PASSWORD = None

        try:
            SMTP_USER = configuration.get('smtp', 'SMTP_USER')
            SMTP_PASSWORD = configuration.get('smtp', 'SMTP_PASSWORD')
        except AirflowConfigException:
            logging.debug("No user/password found for SMTP, so logging in with no authentication.")

        if not dryrun:
            s = smtplib.SMTP_SSL(SMTP_HOST, SMTP_PORT) if SMTP_SSL else smtplib.SMTP(SMTP_HOST, SMTP_PORT)
            if SMTP_STARTTLS:
                s.starttls()
            if SMTP_USER and SMTP_PASSWORD:
                s.login(SMTP_USER, SMTP_PASSWORD)
            logging.info("Sent an alert email to " + str(e_to))
            s.sendmail(e_from, e_to, mime_msg.as_string())
            s.quit()


class Weixin():

    def send(self, to, title, body):
        tousers = self.get_method_list(to)
        message = title.encode("utf-8") + "\n" + body.encode("utf-8")
        try:
            with open('/data1/airflow/myscripts/monitor/data', 'r') as f:
                token = f.read()
            result = self.SendMessage(tousers, token, message)
            if result['errmsg'] != "ok":
                token = self.GetToken("ww8385ff43f8e787f7", "WYsOoloiFhAwS8p9X_wE1uDW_Z6OuaadP70d1Ke2GUM")
                result = self.SendMessage(tousers, token, message)
            if result['invaliduser'] == "":
                logging.info("Sent an alert weixin to [{0}]".format(to))
            else:
                logging.error("Fail sent alert weixin to [{0}]".format(result["invaliduser"]))
        except Exception:
            logging.error("Fail sent alert weixin")


    def GetToken(self, CorpID, Secret):
        tokenurl = 'https://qyapi.weixin.qq.com/cgi-bin/gettoken?corpid=%s&corpsecret=%s' % (CorpID, Secret)
        response = urllib2.urlopen(tokenurl)
        html = response.read().strip()
        ret = json.loads(html)
        access_token = ret['access_token']
        with open('/data1/airflow/myscripts/monitor/data', 'w') as f:
            f.write(access_token)
        return access_token

    def SendMessage(self, to, Token, message):
        url = 'https://qyapi.weixin.qq.com/cgi-bin/message/send?access_token=%s' % Token
        values = {
            "touser": to,
            "toparty": "",
            "totag": "",
            "msgtype": "text",
            "agentid": 1000005,
            "text": {
                "content": message
            },
            "safe": "0"
        }
        data = json.dumps(values, ensure_ascii=False)
        req = urllib2.Request(url, data)
        req.add_header('Content-Type', 'application/json')
        req.add_header('encoding', 'utf-8')
        response = urllib2.urlopen(req)
        result = response.read().strip()
        result = json.loads(result)
        return result

    def get_method_list(self, to_weixins):

        return "|".join(to_weixins)


class Phone():
    def send(self, to_phones, title, body):
        data = {
            "app": "9b6b0150-f7ab-cf14-dcbe-c87e68cec16c",
            "eventType": "trigger",
            "alarmName": title,
            "alarmContent": body
        }
        headers = {
            "Content-type": "application/json"
        }
        url = "http://api.onealert.com/alert/api/event"
        data = json.dumps(data, ensure_ascii=False)
        resp = requests.post(url, data=data, headers=headers)
        result = json.loads(resp.text)
        if result["result"] != "success":
            logging.error("Fail sent alert phone")
        else:
            logging.info("Sent a alert phone")
