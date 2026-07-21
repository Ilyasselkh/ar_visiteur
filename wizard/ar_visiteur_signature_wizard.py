from odoo import fields, models, _
from odoo.exceptions import ValidationError


class ArVisiteurSignatureWizard(models.TransientModel):
    _name = "ar.visiteur.signature.wizard"
    _description = "Signature visiteur"

    visiteur_id = fields.Many2one("ar.visiteur", string="Visite", required=True, readonly=True)
    signature = fields.Binary(string="Signature", required=True)

    def action_valider_signature(self):
        self.ensure_one()
        if not self.signature:
            raise ValidationError(_("Veuillez saisir la signature du visiteur."))
        self.visiteur_id.write({
            "signature": self.signature,
            "signature_done": True,
            "signature_date": fields.Datetime.now(),
            "signature_user_id": self.env.user.id,
        })
        self.visiteur_id._generate_signed_visit_pdf_attachment()
        self.visiteur_id.action_archiver()
        return {"type": "ir.actions.client", "tag": "reload"}
