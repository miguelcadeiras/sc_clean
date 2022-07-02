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
    # print("sendAlert00")
    text_content = message
    html_content = htmly.render(context)
    new_message = EmailMultiAlternatives(subject='ALERT1- '+Subject,
                                           from_email='cubikalert@smartcubik.com',
                                           to=list_mails,
                                           # bcc=,
                                           body=text_content,
                                           )
    new_message.attach_alternative(html_content, "text/html")
    email_messages.append(new_message)
    # print(new_message)
    # print("sendAlert01")
    connection = get_connection(fail_silently=False)
    # Manually open the connection
    # print("sendAlert02")
    try:
        connection.open()
        # print("sendAlert03")
        connection.send_messages(email_messages)
        # We need to manually close the connection.
        print("mail_alerts SENT!!! ", "#" * 20)
        connection.close()
    except:
        print("mail couldn't be sent :-(")