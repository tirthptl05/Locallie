def send_emergency_email(to_email, from_email, city, lat, lon):
    from sendgrid import SendGridAPIClient
    from sendgrid.helpers.mail import Mail
    import os

    location_link = f"https://maps.google.com/?q={lat},{lon}"
    subject = f"🚨 Emergency Alert from {from_email} in {city}"
    content = f"""
    A tourist triggered an emergency alert:

    • Email: {from_email}
    • City: {city}
    • Location: {location_link}

    Please respond immediately.
    """

    message = Mail(
        from_email='tirthapatel1115@gmail.com',  # ✅ verified sender
        to_emails=to_email,
        subject=subject,
        plain_text_content=content
    )

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        sg.send(message)
        print("✅ Email sent to", to_email)
        return True
    except Exception as e:
        print("❌ Email sending failed:", e)
        raise e  # So Flask can catch it and return proper error
