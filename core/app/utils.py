import pandas as pd
from django.core.mail import BadHeaderError, send_mail,EmailMessage,EmailMultiAlternatives,send_mass_mail,get_connection
from django.template.loader import get_template,render_to_string


def exportData(array):
    df = pd.DataFrame({'a':array})
    df = df.set_index('a').T
    return df.to_csv('yourData.csv',index=False)


def sendAlert(list_mails,Subject="",message=""):
    email_messages = []

    htmly = get_template('emails/alert_pause.html')
    context = {}

    text_content = message
    html_content = htmly.render(context)
    new_message = EmailMultiAlternatives(subject='ALERT- '+Subject,
                                           from_email='alert@smartcubik.com',
                                           to=[],
                                           bcc=list_mails,
                                           body=text_content,
                                           )
    new_message.attach_alternative(html_content, "text/html")
    email_messages.append(new_message)

    connection = get_connection()
    # Manually open the connection
    connection.open()
    connection.send_messages(email_messages)
    # We need to manually close the connection.
    connection.close()
    # print("mail_alerts SENT!!! ","#"*20)