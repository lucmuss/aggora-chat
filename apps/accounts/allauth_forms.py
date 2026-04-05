from allauth.account.forms import ResetPasswordForm, ResetPasswordKeyForm


class StyledResetPasswordForm(ResetPasswordForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["email"].widget.attrs.update(
            {
                "placeholder": "you@example.com",
                "autocomplete": "email",
                "spellcheck": "false",
            }
        )


class StyledResetPasswordKeyForm(ResetPasswordKeyForm):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, placeholder in {
            "password1": "New password",
            "password2": "Repeat new password",
        }.items():
            self.fields[field_name].widget.attrs.update(
                {
                    "placeholder": placeholder,
                    "autocomplete": "new-password",
                }
            )
