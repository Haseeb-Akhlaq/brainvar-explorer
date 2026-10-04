"""
The account invitation sent from the admin panel.

An account created in the panel has no password and cannot sign in. Inviting
generates one, activates the account and emails the credentials — the same
shape as FLOW's welcome email, with the BrainVar mark at the top.

The logo is attached and referenced by Content-ID rather than linked. Most
mail clients block remote images by default, and a linked logo would also
break whenever the site was unreachable; embedding costs a little size and
always renders.
"""

import logging
import secrets
import string
from datetime import datetime
import mimetypes
from email.message import MIMEPart

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

logger = logging.getLogger(__name__)

LOGO_CID = "brainvar-logo"
PASSWORD_LENGTH = 16

# Ambiguous characters are left out: these passwords get read off a screen and
# retyped, and "l" against "1" or "O" against "0" is a support request waiting
# to happen. Excluding them costs about a bit of entropy at this length, which
# a 16-character password can spare.
AMBIGUOUS = "lI1O0"
LOWER = "".join(c for c in string.ascii_lowercase if c not in AMBIGUOUS)
UPPER = "".join(c for c in string.ascii_uppercase if c not in AMBIGUOUS)
DIGITS = "".join(c for c in string.digits if c not in AMBIGUOUS)
SYMBOLS = "!@#$%^&*-_=+?"


def generate_password(length: int = PASSWORD_LENGTH) -> str:
    """
    A random password with at least one character from each class.

    `secrets` rather than `random`: the latter is a Mersenne Twister seeded
    from the clock, and its output is predictable to anyone who can observe a
    few values. This is a credential, so it needs the system CSPRNG.
    """
    alphabet = LOWER + UPPER + DIGITS + SYMBOLS
    chars = [
        secrets.choice(LOWER),
        secrets.choice(UPPER),
        secrets.choice(DIGITS),
        secrets.choice(SYMBOLS),
    ]
    chars += [secrets.choice(alphabet) for _ in range(length - len(chars))]
    # Without the shuffle the classes would always appear in the same order,
    # which hands an attacker the first four positions for free.
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def send_invitation(user, password: str) -> None:
    """
    Email `user` their credentials.

    Raises whatever the mail backend raises; the caller rolls the password
    back so an account is never left with credentials nobody received.
    """
    context = {
        "user_name": user.get_short_name(),
        "user_email": user.email,
        "password": password,
        "login_url": settings.APP_LOGIN_URL,
        "support_email": settings.EMAIL_SUPPORT_ADDRESS,
        "logo_cid": LOGO_CID,
        "year": datetime.now().year,
    }

    html = render_to_string("emails/invitation.html", context)
    text = render_to_string("emails/invitation.txt", context)

    message = EmailMultiAlternatives(
        subject="Your BrainVar Trajectory Explorer account",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html, "text/html")
    _attach_logo(message)
    message.send(fail_silently=False)

    # The address is worth logging; the password very much is not.
    logger.info("INVITATION_SENT | %s", user.email)


def _attach_logo(message: EmailMultiAlternatives) -> None:
    """
    Attach the mark inline, if it is present.

    Built as an `email.message.MIMEPart`: Django 6 removed the undocumented
    `mixed_subtype` attribute and deprecated `MIMEBase` attachments, so this
    is the supported way to hand it a part with headers of its own.

    A missing file is not worth failing an invitation over — the recipient
    still gets working credentials — so this degrades rather than raises.
    """
    path = settings.EMAIL_LOGO_PATH
    try:
        data = path.read_bytes()
    except OSError:
        logger.warning("Invitation logo missing at %s; sending without it", path)
        return

    mimetype, _ = mimetypes.guess_type(path.name)
    maintype, _, subtype = (mimetype or "image/png").partition("/")

    part = MIMEPart()
    part.set_content(data, maintype=maintype, subtype=subtype)
    part.add_header("Content-ID", f"<{LOGO_CID}>")
    # "inline" keeps it out of the client's attachment list, where a logo
    # would otherwise look like a file the recipient is meant to open.
    part.add_header("Content-Disposition", "inline", filename=path.name)
    message.attach(part)
