from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArVisiteurConfig(models.Model):
    _name = "ar.visiteur.config"
    _description = "AR - Visiteur - Paramétrage"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "sequence, id"

    name = fields.Char(string="Nom", required=True, default="Document d'accueil", tracking=True)
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True, tracking=True)
    pdf_file = fields.Binary(string="PDF", attachment=True, required=True, tracking=True)
    pdf_filename = fields.Char(string="Nom du fichier", tracking=True)
    survey_id = fields.Many2one("survey.survey", string="Quiz visiteur", tracking=True)
    quiz_validity_months = fields.Integer(string="Validité du quiz (mois)", default=3, tracking=True)

    @api.constrains("pdf_filename")
    def _check_pdf_filename(self):
        for rec in self:
            if rec.pdf_filename and not rec.pdf_filename.lower().endswith(".pdf"):
                raise ValidationError(_("Le document paramétré doit être un fichier PDF."))

    @api.constrains("quiz_validity_months")
    def _check_quiz_validity_months(self):
        for rec in self:
            if rec.quiz_validity_months < 0:
                raise ValidationError(_("La validité du quiz ne peut pas être négative."))
