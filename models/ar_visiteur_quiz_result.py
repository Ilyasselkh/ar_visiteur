from odoo import api, fields, models, _


class ArVisiteurQuizResult(models.Model):
    _name = "ar.visiteur.quiz.result"
    _description = "AR - Visiteur - Résultat quiz"
    _order = "quiz_date desc, id desc"
    _rec_name = "name"

    name = fields.Char(string="Référence", compute="_compute_name", store=True)
    visiteur_id = fields.Many2one("ar.visiteur", string="Demande", required=True, ondelete="cascade", index=True)
    reference = fields.Char(string="Référence visite", related="visiteur_id.name", store=True)
    nom = fields.Char(string="Nom", related="visiteur_id.nom", store=True)
    prenom = fields.Char(string="Prénom", related="visiteur_id.prenom", store=True)
    cin = fields.Char(string="CIN", related="visiteur_id.cin", store=True)
    personne_a_visiter_id = fields.Many2one(
        "hr.employee",
        string="Personne visitée",
        related="visiteur_id.personne_a_visiter_id",
        store=True,
        index=True,
    )
    date_entree = fields.Date(string="Date d'entrée", related="visiteur_id.date_entree", store=True)
    date_sortie = fields.Date(string="Date de sortie", related="visiteur_id.date_sortie", store=True)
    duree_visite = fields.Float(string="Durée de visite", related="visiteur_id.duree_visite", store=True)
    survey_id = fields.Many2one("survey.survey", string="Quiz", index=True)
    survey_user_input_id = fields.Many2one("survey.user_input", string="Réponse quiz", index=True)
    quiz_status = fields.Selection(
        [
            ("required", "À faire"),
            ("done", "Effectué"),
            ("ignored", "Ignoré"),
        ],
        string="Statut",
        default="required",
        required=True,
        index=True,
    )
    quiz_date = fields.Datetime(string="Date du quiz", index=True)
    quiz_skipped_reason = fields.Char(string="Motif d'ignorance")
    score = fields.Float(string="Score", compute="_compute_survey_metrics", store=True)
    score_percentage = fields.Float(string="Pourcentage", compute="_compute_survey_metrics", store=True)
    quiz_success = fields.Boolean(string="Réussi", compute="_compute_survey_metrics", store=True)
    question_count = fields.Integer(string="Questions", compute="_compute_survey_metrics", store=True)
    answer_count = fields.Integer(string="Réponses", compute="_compute_survey_metrics", store=True)

    @api.depends("reference", "nom", "prenom", "cin")
    def _compute_name(self):
        for rec in self:
            visitor = " ".join(part for part in [rec.nom, rec.prenom] if part)
            rec.name = "%s - %s" % (rec.reference or _("Quiz"), visitor or rec.cin or _("Visiteur"))

    def _get_float_from_record(self, record, field_names):
        for field_name in field_names:
            if field_name in record._fields:
                return float(record[field_name] or 0.0)
        return 0.0

    def _get_answer_lines(self, answer):
        if answer and "user_input_line_ids" in answer._fields:
            lines = answer.user_input_line_ids
            if "skipped" in lines._fields:
                lines = lines.filtered(lambda line: not line.skipped)
            return lines
        return self.env["survey.user_input.line"]

    def _get_manual_score(self, answer):
        lines = self._get_answer_lines(answer)
        if lines and "answer_score" in lines._fields:
            return sum(lines.mapped("answer_score"))
        return 0.0

    def _get_question_max_score(self, question):
        score = self._get_float_from_record(question, ["answer_score"])
        if score:
            return score
        answer_fields = ["suggested_answer_ids", "answer_ids"]
        for field_name in answer_fields:
            if field_name in question._fields:
                answers = question[field_name]
                if answers and "answer_score" in answers._fields:
                    scores = [answer.answer_score for answer in answers if answer.answer_score > 0]
                    return max(scores) if scores else 0.0
        return 0.0

    def _get_manual_max_score(self, survey):
        if not survey or "question_ids" not in survey._fields:
            return 0.0
        return sum(self._get_question_max_score(question) for question in survey.question_ids)

    @api.depends("survey_id", "survey_user_input_id")
    def _compute_survey_metrics(self):
        for rec in self:
            answer = rec.survey_user_input_id.sudo()
            survey = rec.survey_id.sudo()
            score = self._get_float_from_record(answer, ["scoring_total", "quizz_score", "score"]) if answer else 0.0
            if not score:
                score = rec._get_manual_score(answer)
            score_percentage = self._get_float_from_record(
                answer,
                ["scoring_percentage", "scoring_percentage_obtained"],
            ) if answer else 0.0
            if not score_percentage:
                max_score = rec._get_manual_max_score(survey)
                score_percentage = (score / max_score) * 100.0 if max_score else 0.0
            success_min = self._get_float_from_record(survey, ["scoring_success_min"])
            rec.score = score
            rec.score_percentage = score_percentage
            rec.quiz_success = bool(answer["scoring_success"]) if answer and "scoring_success" in answer._fields else False
            if not rec.quiz_success and success_min:
                rec.quiz_success = score_percentage >= success_min
            rec.question_count = len(survey.question_ids) if survey and "question_ids" in survey._fields else 0
            rec.answer_count = len(rec._get_answer_lines(answer))

    def action_open_visiteur(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Demande visiteur"),
            "res_model": "ar.visiteur",
            "res_id": self.visiteur_id.id,
            "view_mode": "form",
        }

    def action_open_survey_answer(self):
        self.ensure_one()
        if not self.survey_user_input_id:
            return False
        return {
            "type": "ir.actions.act_window",
            "name": _("Réponse quiz"),
            "res_model": "survey.user_input",
            "res_id": self.survey_user_input_id.id,
            "view_mode": "form",
        }


class HrEmployee(models.Model):
    _inherit = "hr.employee"

    ar_visiteur_quiz_result_count = fields.Integer(
        string="Résultats quiz visiteurs",
        compute="_compute_ar_visiteur_quiz_result_count",
    )

    def _compute_ar_visiteur_quiz_result_count(self):
        grouped = self.env["ar.visiteur.quiz.result"].sudo().read_group(
            [("personne_a_visiter_id", "in", self.ids)],
            ["personne_a_visiter_id"],
            ["personne_a_visiter_id"],
        )
        counts = {
            item["personne_a_visiter_id"][0]: item.get("personne_a_visiter_id_count", item.get("__count", 0))
            for item in grouped
        }
        for employee in self:
            employee.ar_visiteur_quiz_result_count = counts.get(employee.id, 0)

    def action_view_ar_visiteur_quiz_results(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Résultats quiz visiteurs"),
            "res_model": "ar.visiteur.quiz.result",
            "view_mode": "list,kanban,form,pivot,graph",
            "domain": [("personne_a_visiter_id", "=", self.id)],
            "context": {"search_default_group_visitor": 1},
        }
