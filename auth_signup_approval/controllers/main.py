import logging
from odoo import _, SUPERUSER_ID
from odoo.http import request, route
from odoo.addons.auth_signup.controllers.main import AuthSignupHome


_logger = logging.getLogger(__name__)

try:
    from email_validator import validate_email, EmailSyntaxError, \
        EmailUndeliverableError
except ImportError:
    # pragma: no-cover
    try:
        from validate_email import validate_email as _validate

        class EmailSyntaxError(Exception):
            message = False

        class EmailUndeliverableError(Exception):
            message = False

        def validate_email(*args, **kwargs):
            if not _validate(*args, **kwargs):
                raise EmailSyntaxError

    except ImportError:
        _logger.debug("Cannot import `email_validator`.")
    else:
        _logger.warning("Install `email_validator` to get full support.")


class SignupVerifyEmail(AuthSignupHome):

    @route()
    def web_auth_signup(self, *args, **kw):
        if (request.params.get("login") and
                not request.params.get("password")):
            return self.passwordless_signup(request.params)
        else:
            return super(SignupVerifyEmail, self).web_auth_signup(*args, **kw)

    @staticmethod
    def check_format_email(login):
        error = ""
        try:
            validate_email(login or "")
        except EmailSyntaxError as e:
            error = getattr(
                e,
                "message",
                _("That does not seem to be an email address."),
            )
        except EmailUndeliverableError as e:
            error = str(e)
        except Exception as e:
            error = str(e)
        return error

    @staticmethod
    def create_user(values, token, login):
        sudo_users = (request.env["res.users"]
                      .with_context(create_user=True).sudo())
        try:
            with request.cr.savepoint():
                sudo_users.signup(values, token)
        except Exception as error:
            # Duplicate key or wrong SMTP settings, probably
            _logger.exception(error)
            if request.env["res.users"].sudo().search(
               [("login", "=", login)]):
                return _("Another user is already registered using this email"
                         " address.")
            # Agnostic message for security
            return _("Something went wrong, please try again later or"
                     " contact us.")
        return False

    def passwordless_signup(self, values):
        qcontext = self.get_auth_signup_qcontext()
        login = values.get("login", "")
        message = self.check_format_email(login) or qcontext.get('error', '')
        if message:
            qcontext["error"] = message
            return request.render("auth_signup.signup", qcontext)

        values["email"] = values.get("email", login)
        # preserve user lang
        supported_langs = [lang['code'] for lang in request.env['res.lang'].sudo().search_read([], ['code'])]
        if request.lang in supported_langs:
            values['lang'] = request.lang
        # Remove password
        values["password"] = ""

        message = self.create_user(values, qcontext.get("token"), login)
        if message:
            qcontext["error"] = message
            return request.render("auth_signup.signup", qcontext)

        qcontext["message"] = _(
            """Thank you for signing up in our site. Your information it's being reviewed by one of our administrators. As soon as your account review is finished, we will email you with instructions on how to activate it."""
        )

        return request.render("auth_signup.reset_password", qcontext)
