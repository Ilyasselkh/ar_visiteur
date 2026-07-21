import base64
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
            ("quiz", "Quiz à faire"),
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
    quiz_required = fields.Boolean(string="Quiz requis", readonly=True, copy=False, tracking=True)
    quiz_done = fields.Boolean(string="Quiz effectué", readonly=True, copy=False, tracking=True)
    quiz_date = fields.Datetime(string="Date du quiz", readonly=True, copy=False, tracking=True)
    quiz_skipped_reason = fields.Char(string="Quiz ignoré", readonly=True, copy=False)
    survey_id = fields.Many2one("survey.survey", string="Quiz", readonly=True, copy=False)
    survey_user_input_id = fields.Many2one("survey.user_input", string="Réponse quiz", readonly=True, copy=False)
    quiz_result_ids = fields.One2many("ar.visiteur.quiz.result", "visiteur_id", string="Résultats quiz", readonly=True)
    quiz_result_count = fields.Integer(string="Résultats quiz", compute="_compute_quiz_result_count")
    signature = fields.Binary(string="Signature visiteur", attachment=True, readonly=True, copy=False)
    signature_done = fields.Boolean(string="Signature effectuée", readonly=True, copy=False, tracking=True)
    signature_date = fields.Datetime(string="Date de signature", readonly=True, copy=False, tracking=True)
    signature_user_id = fields.Many2one("res.users", string="Signature enregistrée par", readonly=True, copy=False)
    signature_visitor_name = fields.Char(
        string="Signature enregistrée par",
        compute="_compute_signature_visitor_name",
    )
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

    def _compute_quiz_result_count(self):
        grouped = self.env["ar.visiteur.quiz.result"].sudo().read_group(
            [("visiteur_id", "in", self.ids)],
            ["visiteur_id"],
            ["visiteur_id"],
        )
        counts = {item["visiteur_id"][0]: item.get("visiteur_id_count", item.get("__count", 0)) for item in grouped}
        for rec in self:
            rec.quiz_result_count = counts.get(rec.id, 0)

    @api.depends("nom", "prenom")
    def _compute_signature_visitor_name(self):
        for rec in self:
            rec.signature_visitor_name = " ".join(part for part in [rec.nom, rec.prenom] if part)

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

    def _get_active_config(self):
        return self.env["ar.visiteur.config"].search([("active", "=", True)], order="sequence, id", limit=1)

    def _subtract_months(self, date_value, months):
        year = date_value.year
        month = date_value.month - max(months, 0)
        while month <= 0:
            month += 12
            year -= 1
        day = min(date_value.day, 28)
        return date_value.replace(year=year, month=month, day=day)

    def _find_recent_quiz(self, validity_months):
        self.ensure_one()
        if not self.cin:
            return False
        limit_dt = self._subtract_months(fields.Datetime.now(), validity_months)
        return self.search(
            [
                ("id", "!=", self.id),
                ("cin", "=", self.cin),
                ("quiz_done", "=", True),
                ("quiz_date", ">=", limit_dt),
            ],
            order="quiz_date desc, id desc",
            limit=1,
        )

    def _prepare_quiz_after_exit(self):
        config = self._get_active_config()
        survey = config.survey_id if config else False
        validity_months = config.quiz_validity_months if config and config.quiz_validity_months else 3
        for rec in self:
            if not survey:
                rec.write({
                    "quiz_required": False,
                    "quiz_done": False,
                    "quiz_date": False,
                    "quiz_skipped_reason": _("Aucun quiz n'est configuré."),
                    "survey_id": False,
                    "survey_user_input_id": False,
                    "state": "sorti",
                })
                continue
            recent_quiz = rec._find_recent_quiz(validity_months)
            if recent_quiz:
                rec.write({
                    "quiz_required": False,
                    "quiz_done": True,
                    "quiz_date": recent_quiz.quiz_date,
                    "quiz_skipped_reason": _("Quiz déjà effectué le %s.") % fields.Datetime.to_string(recent_quiz.quiz_date),
                    "survey_id": survey.id,
                    "survey_user_input_id": recent_quiz.survey_user_input_id.id,
                    "state": "sorti",
                })
                rec._sync_quiz_result()
            else:
                rec.write({
                    "quiz_required": True,
                    "quiz_done": False,
                    "quiz_date": False,
                    "quiz_skipped_reason": False,
                    "survey_id": survey.id,
                    "survey_user_input_id": False,
                    "state": "quiz",
                })
                rec._sync_quiz_result()

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
                }
            )
        self._prepare_quiz_after_exit()
        if len(self) == 1 and self.state == "quiz":
            return self.action_repondre_quiz()
        return True

    def action_archiver(self):
        for rec in self:
            if rec.state == "en_cours":
                raise ValidationError(_("Vous devez d'abord marquer la sortie avant d'archiver la visite."))
            if rec.quiz_required and not rec.quiz_done:
                raise ValidationError(_("Vous devez d'abord valider le quiz avant d'archiver la visite."))
            if not rec.signature_done:
                raise ValidationError(_("Vous devez enregistrer la signature du visiteur avant d'archiver la visite."))
            rec.state = "archive"

    def action_remettre_en_cours(self):
        self.mapped("quiz_result_ids").unlink()
        self.write({
            "state": "en_cours",
            "date_sortie": False,
            "heure_sortie": False,
            "sortie_marquee": False,
            "quiz_required": False,
            "quiz_done": False,
            "quiz_date": False,
            "quiz_skipped_reason": False,
            "survey_id": False,
            "survey_user_input_id": False,
            "signature": False,
            "signature_done": False,
            "signature_date": False,
            "signature_user_id": False,
        })

    def action_save_visiteur(self):
        self._send_visit_notification()
        return True

    def action_signer(self):
        self.ensure_one()
        if self.state != "sorti":
            raise ValidationError(_("La signature est disponible uniquement après la sortie du visiteur."))
        return {
            "type": "ir.actions.act_window",
            "name": _("Signature visiteur"),
            "res_model": "ar.visiteur.signature.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_visiteur_id": self.id},
        }

    def _generate_signed_visit_pdf_attachment(self):
        self.ensure_one()
        if not self.signature_done or not self.signature:
            return False
        report = self.env.ref("ar_visiteur.action_report_ar_visiteur_signed", raise_if_not_found=False)
        if not report:
            return False
        try:
            pdf_content, _content_type = report._render_qweb_pdf(report.report_name, [self.id])
        except TypeError:
            pdf_content, _content_type = report._render_qweb_pdf([self.id])
        filename = "Fiche visiteur - %s.pdf" % (self.name or _("Visiteur"))
        attachment = self.env["ir.attachment"].create({
            "name": filename,
            "type": "binary",
            "datas": base64.b64encode(pdf_content).decode(),
            "res_model": self._name,
            "res_id": self.id,
            "mimetype": "application/pdf",
        })
        self.message_post(
            body=_("Fiche visiteur générée automatiquement."),
            attachment_ids=[attachment.id],
            subtype_xmlid="mail.mt_note",
        )
        return attachment

    def action_repondre_quiz(self):
        self.ensure_one()
        if not self.survey_id:
            raise ValidationError(_("Aucun quiz n'est configuré."))
        if not self.survey_user_input_id:
            vals = {
                "survey_id": self.survey_id.id,
            }
            self.survey_user_input_id = self.env["survey.user_input"].sudo().create(vals)

        survey_token = getattr(self.survey_id, "access_token", False)
        answer_token = getattr(self.survey_user_input_id, "access_token", False)
        url = False
        if hasattr(self.survey_user_input_id, "_get_start_url"):
            try:
                url = self.survey_user_input_id._get_start_url()
            except TypeError:
                url = False
        if not url and survey_token and answer_token:
            url = f"/survey/start/{survey_token}?answer_token={answer_token}"
        elif not url and survey_token:
            url = f"/survey/start/{survey_token}"
        if not url:
            raise ValidationError(_("Impossible de générer le lien du quiz."))
        return {"type": "ir.actions.act_url", "url": url, "target": "new"}

    def action_verifier_quiz(self):
        for rec in self:
            if not rec.survey_user_input_id:
                raise ValidationError(_("Aucune réponse de quiz n'est liée à cette visite."))
            if rec.survey_user_input_id.state != "done":
                raise ValidationError(_("Le quiz n'est pas encore terminé."))
            rec.write({
                "quiz_done": True,
                "quiz_date": fields.Datetime.now(),
                "quiz_required": False,
                "state": "sorti",
            })
            rec._sync_quiz_result()

    def _sync_quiz_result(self):
        Result = self.env["ar.visiteur.quiz.result"].sudo()
        for rec in self:
            if not rec.survey_id and not rec.survey_user_input_id and not rec.quiz_required and not rec.quiz_done:
                continue
            if rec.quiz_skipped_reason:
                status = "ignored"
            elif rec.quiz_done:
                status = "done"
            else:
                status = "required"
            vals = {
                "visiteur_id": rec.id,
                "survey_id": rec.survey_id.id,
                "survey_user_input_id": rec.survey_user_input_id.id,
                "quiz_status": status,
                "quiz_date": rec.quiz_date or fields.Datetime.now(),
                "quiz_skipped_reason": rec.quiz_skipped_reason,
            }
            result = Result.search([("visiteur_id", "=", rec.id)], limit=1)
            if result:
                result.write(vals)
            else:
                result = Result.create(vals)
            result._compute_survey_metrics()

    def action_view_quiz_results(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Résultats quiz"),
            "res_model": "ar.visiteur.quiz.result",
            "view_mode": "list,kanban,form,pivot,graph",
            "domain": [("visiteur_id", "=", self.id)],
            "context": {"default_visiteur_id": self.id},
        }

    def action_supprimer(self):
        for rec in self:
            if rec.state != "en_cours":
                raise ValidationError(_("Vous pouvez supprimer uniquement une demande en cours."))
        self.sudo().unlink()
        return {
            "type": "ir.actions.act_window",
            "name": _("Demande"),
            "res_model": "ar.visiteur",
            "view_mode": "list,form",
            "domain": [("state", "=", "en_cours")],
            "context": {"search_default_en_cours": 1},
        }

    def action_repondre_quiz(self):
        self.ensure_one()
        if not self.survey_id:
            raise ValidationError(_("Aucun quiz n'est configuré."))
        self._ensure_survey_answer()
        return {
            "type": "ir.actions.act_window",
            "name": _("Quiz visiteur"),
            "res_model": "ar.visiteur.quiz.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_visiteur_id": self.id},
        }

    def _ensure_survey_answer(self):
        self.ensure_one()
        if self.survey_user_input_id:
            return self.survey_user_input_id
        survey = self.survey_id.sudo()
        answer = False
        if hasattr(survey, "_create_answer"):
            create_attempts = [
                {"user": self.env.user, "partner": self.env.user.partner_id, "check_attempts": False},
                {"user": self.env.user, "check_attempts": False},
                {"partner": self.env.user.partner_id, "check_attempts": False},
                {"check_attempts": False},
                {},
            ]
            for kwargs in create_attempts:
                try:
                    answer = survey._create_answer(**kwargs)
                    break
                except TypeError:
                    continue
        if not answer:
            vals = {"survey_id": survey.id}
            user_input_model = self.env["survey.user_input"]
            if "partner_id" in user_input_model._fields and self.env.user.partner_id:
                vals["partner_id"] = self.env.user.partner_id.id
            if "email" in user_input_model._fields:
                vals["email"] = self._clean_header(self.env.user.partner_id.email or self.env.user.email or "")
            answer = user_input_model.sudo().create(vals)
        self.sudo().write({"survey_user_input_id": answer.id})
        return answer

    def _get_quiz_url(self):
        self.ensure_one()
        answer = self._ensure_survey_answer()
        survey_token = getattr(self.survey_id, "access_token", False)
        answer_token = getattr(answer, "access_token", False)
        url = False
        if hasattr(answer, "_get_start_url"):
            try:
                url = answer._get_start_url()
            except TypeError:
                url = False
        if not url and survey_token and answer_token:
            url = f"/survey/start/{survey_token}?answer_token={answer_token}"
        elif not url and survey_token:
            url = f"/survey/start/{survey_token}"
        if not url:
            raise ValidationError(_("Impossible de générer le lien du quiz."))
        return url

    def unlink(self):
        for rec in self:
            if rec.state != "en_cours":
                raise ValidationError(_("Vous pouvez supprimer uniquement une demande en cours."))
        return super().unlink()
