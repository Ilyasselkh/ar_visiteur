from html import escape
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArVisiteurQuizWizard(models.TransientModel):
    _name = "ar.visiteur.quiz.wizard"
    _description = "Quiz visiteur"

    visiteur_id = fields.Many2one("ar.visiteur", string="Visite", required=True, readonly=True)
    survey_url = fields.Char(string="Lien du quiz", compute="_compute_survey_content")
    survey_html = fields.Html(
        string="Quiz",
        compute="_compute_survey_content",
        sanitize=False,
    )

    @api.depends("visiteur_id", "visiteur_id.survey_user_input_id")
    def _compute_survey_content(self):
        for wizard in self:
            url = wizard.visiteur_id._get_quiz_url() if wizard.visiteur_id else False
            url = wizard._add_popup_context_to_url(url) if url else False
            wizard.survey_url = url
            wizard.survey_html = (
                f'<iframe class="ar_visiteur_quiz_iframe" '
                f'src="{escape(url)}" '
                f'title="{escape(_("Quiz visiteur"))}"></iframe>'
                if url
                else False
            )

    def _add_popup_context_to_url(self, url):
        parts = urlsplit(url)
        query = dict(parse_qsl(parts.query, keep_blank_values=True))
        query["ar_visiteur_popup"] = "1"
        return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))

    def action_verifier_quiz(self):
        self.ensure_one()
        if not self.visiteur_id:
            raise ValidationError(_("Aucune visite n'est liée à ce quiz."))
        self.visiteur_id.action_verifier_quiz()
        return {"type": "ir.actions.client", "tag": "reload"}
