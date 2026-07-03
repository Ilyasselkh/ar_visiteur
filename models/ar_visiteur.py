from datetime import datetime
from html import escape
from urllib.parse import quote

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class ArVisiteur(models.Model):
    _name = "ar.visiteur"
    _description = "AR - Visiteur"
    _inherit = ["mail.thread", "mail.activity.mixin"]
    _order = "date_entree desc, heure_entree desc, id desc"

    name = fields.Char(string="Référence", default="Nouveau", readonly=True, copy=False, tracking=True)
    active = fields.Boolean(default=True, tracking=True)
    state = fields.Selection(
        [
            ("en_cours", "En cours"),
            ("sorti", "Sorti"),
            ("archive", "Archive"),
        ],
        string="État",
        default="en_cours",
        required=True,
        tracking=True,
    )
    date_entree = fields.Date(
        string="Date d'entrée",
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    heure_entree = fields.Float(
        string="Heure d'entrée",
        default=lambda self: self._default_heure(),
        required=True,
        tracking=True,
    )
    nom = fields.Char(string="Nom", required=True, tracking=True)
    prenom = fields.Char(string="Prénom", required=True, tracking=True)
    cin = fields.Char(string="CIN", required=True, tracking=True)
    visite_terrain = fields.Selection(
        [
            ("oui", "Oui"),
            ("non", "Non"),
        ],
        string="Visite terrain",
        default="oui",
        required=True,
        tracking=True,
    )
    personne_a_visiter_id = fields.Many2one(
        "hr.employee",
        string="Personne à visiter",
        required=True,
        tracking=True,
        help="Personne à visiter.",
    )
    visite_notification_sent = fields.Boolean(string="Notification envoyée", readonly=True, copy=False)
    sortie_marquee = fields.Boolean(string="Sortie marquée", readonly=True, copy=False)
    date_sortie = fields.Date(string="Date de sortie", tracking=True)
    heure_sortie = fields.Float(string="Heure de sortie", tracking=True)
    duree_visite = fields.Float(string="Durée de visite", compute="_compute_duree_visite", store=True)
    pdf_accueil = fields.Binary(string="Document d'accueil", compute="_compute_pdf_accueil")
    pdf_accueil_filename = fields.Char(string="Nom du document", compute="_compute_pdf_accueil")
    pdf_accueil_html = fields.Html(
        string="Aperçu du document d'accueil",
        compute="_compute_pdf_accueil",
        sanitize=False,
    )

    def _default_heure(self):
        now = fields.Datetime.context_timestamp(self, datetime.utcnow())
        return now.hour + (now.minute / 60.0)

    @api.model_create_multi
    def create(self, vals_list):
        sequence = self.env["ir.sequence"]
        for vals in vals_list:
            if vals.get("name", "Nouveau") == "Nouveau":
                vals["name"] = sequence.next_by_code("ar.visiteur") or "Nouveau"
        records = super().create(vals_list)
        records._send_visit_notification()
        return records

    def _clean_header(self, value):
        if not value:
            return False
        return str(value).replace("\n", "").replace("\r", "").strip()

    def _get_employee_email(self, employee):
        if not employee:
            return False
        employee = employee.sudo()
        email = False
        if employee.user_id:
            email = employee.user_id.partner_id.email or employee.user_id.email
        if not email:
            email = employee.work_email
        return self._clean_header(email) if email else False

    def _send_visit_notification(self):
        template = self.env.ref("ar_visiteur.mail_template_ar_visiteur_notification", raise_if_not_found=False)
        if not template:
            return
        for rec in self:
            if rec.visite_notification_sent or not rec.personne_a_visiter_id:
                continue
            email_to = rec._get_employee_email(rec.personne_a_visiter_id)
            if not email_to:
                rec.message_post(
                    body=_("Notification non envoyée : la personne à visiter n'a pas d'adresse e-mail professionnelle."),
                    subtype_xmlid="mail.mt_note",
                )
                continue
            reply_to = self.env.user.partner_id.email or self.env.user.email or ""
            email_values = {
                "email_to": rec._clean_header(email_to),
                "reply_to": rec._clean_header(reply_to),
            }
            template.send_mail(rec.id, force_send=True, email_values=email_values)
            rec.visite_notification_sent = True
            rec.message_post(
                body=_("Notification envoyée à %s.") % rec.personne_a_visiter_id.name,
                subtype_xmlid="mail.mt_note",
            )

    @api.depends("date_entree", "heure_entree", "date_sortie", "heure_sortie")
    def _compute_duree_visite(self):
        for rec in self:
            rec.duree_visite = 0.0
            if not all([rec.date_entree, rec.date_sortie, rec.heure_entree is not False, rec.heure_sortie is not False]):
                continue
            entree = datetime.combine(rec.date_entree, datetime.min.time())
            sortie = datetime.combine(rec.date_sortie, datetime.min.time())
            delta_days = (sortie.date() - entree.date()).days
            rec.duree_visite = max((delta_days * 24.0) + rec.heure_sortie - rec.heure_entree, 0.0)

    @api.depends("visite_terrain")
    def _compute_pdf_accueil(self):
        config = self.env["ar.visiteur.config"].search([("active", "=", True)], order="sequence, id", limit=1)
        for rec in self:
            if rec.visite_terrain == "oui" and config:
                rec.pdf_accueil = config.pdf_file
                rec.pdf_accueil_filename = config.pdf_filename
                filename = quote(config.pdf_filename or "document.pdf")
                src = f"/web/content/ar.visiteur.config/{config.id}/pdf_file/{filename}?download=false#zoom=page-fit"
                rec.pdf_accueil_html = (
                    f'<iframe class="ar_visiteur_pdf_iframe" '
                    f'src="{escape(src)}" '
                    f'title="{escape(config.name or "Document d accueil")}"></iframe>'
                )
            else:
                rec.pdf_accueil = False
                rec.pdf_accueil_filename = False
                rec.pdf_accueil_html = False

    @api.constrains("date_entree", "heure_entree", "date_sortie", "heure_sortie")
    def _check_sortie_after_entree(self):
        for rec in self:
            if rec.date_sortie and rec.date_entree and rec.date_sortie < rec.date_entree:
                raise ValidationError(_("La date de sortie ne peut pas être avant la date d'entrée."))
            if (
                rec.date_sortie
                and rec.date_entree
                and rec.date_sortie == rec.date_entree
                and rec.heure_sortie
                and rec.heure_entree
                and rec.heure_sortie < rec.heure_entree
            ):
                raise ValidationError(_("L'heure de sortie ne peut pas être avant l'heure d'entrée."))

    def action_marquer_sortie(self):
        now = fields.Datetime.context_timestamp(self, datetime.utcnow())
        for rec in self:
            rec.write(
                {
                    "date_sortie": now.date(),
                    "heure_sortie": now.hour + (now.minute / 60.0),
                    "sortie_marquee": True,
                    "state": "sorti",
                }
            )

    def action_archiver(self):
        for rec in self:
            if rec.state == "en_cours":
                raise ValidationError(_("Vous devez d'abord marquer la sortie avant d'archiver la visite."))
            rec.state = "archive"

    def action_remettre_en_cours(self):
        self.write({"state": "en_cours", "date_sortie": False, "heure_sortie": False, "sortie_marquee": False})

    def action_save_visiteur(self):
        self._send_visit_notification()
        return True
