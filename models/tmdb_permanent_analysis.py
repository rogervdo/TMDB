from odoo import models, fields, api
from odoo.exceptions import UserError


class TMDBSavedAnalysis(models.Model):
    _name = "tmdb.permanent.analysis"
    _description = "TMDB Saved Analysis"
    _order = "create_date desc"

    # Campos básicos
    name = fields.Char(string="Nombre del Análisis", required=True)
    analysis_type = fields.Selection(
        [
            ("decade", "Análisis por Décadas"),
            ("genre", "Distribución por Géneros"),
            ("rating_vs_popularity", "Calificaciones vs Popularidad"),
            ("gaps", "Identificación de Vacíos"),
            ("comprehensive", "Análisis Completo"),
        ],
        string="Tipo de Análisis",
        required=True,
    )

    # Filtros utilizados
    date_from = fields.Date(string="Fecha Desde")
    date_to = fields.Date(string="Fecha Hasta")
    min_rating = fields.Float(string="Rating Mínimo")
    max_rating = fields.Float(string="Rating Máximo")
    min_popularity = fields.Float(string="Popularidad Mínima")
    max_popularity = fields.Float(string="Popularidad Máxima")

    # Estadísticas generales
    total_movies = fields.Integer(string="Total de Películas")
    avg_rating = fields.Float(string="Rating Promedio", digits=(3, 2))
    avg_popularity = fields.Float(string="Popularidad Promedio", digits=(3, 2))
    date_range = fields.Char(string="Rango de Fechas")

    # Resultados del análisis
    decade_analysis = fields.Text(string="Análisis por Décadas")
    genre_analysis = fields.Text(string="Análisis por Géneros")
    rating_popularity_analysis = fields.Text(string="Análisis Rating vs Popularidad")
    gaps_analysis = fields.Text(string="Análisis de Vacíos")

    # Datos de gráficos (JSON)
    decade_chart_data = fields.Text(string="Datos de Gráfico por Décadas")
    genre_chart_data = fields.Text(string="Datos de Gráfico por Géneros")
    rating_popularity_chart_data = fields.Text(
        string="Datos de Gráfico Rating vs Popularidad"
    )

    # Campos de control
    user_id = fields.Many2one(
        "res.users", string="Usuario", default=lambda self: self.env.user
    )
    create_date = fields.Datetime(string="Fecha de Creación", readonly=True)
    write_date = fields.Datetime(string="Última Modificación", readonly=True)

    # Campos calculados
    analysis_summary = fields.Text(
        string="Resumen del Análisis", compute="_compute_analysis_summary", store=True
    )

    @api.depends("analysis_type", "total_movies", "avg_rating", "avg_popularity")
    def _compute_analysis_summary(self):
        """Calcula un resumen del análisis"""
        for record in self:
            summary_lines = []
            summary_lines.append(f"📊 {record.name}")
            summary_lines.append(
                f"Tipo: {dict(record._fields['analysis_type'].selection).get(record.analysis_type)}"
            )
            summary_lines.append(f"Películas analizadas: {record.total_movies}")
            summary_lines.append(f"Rating promedio: {record.avg_rating:.2f}")
            summary_lines.append(f"Popularidad promedio: {record.avg_popularity:.2f}")
            summary_lines.append(
                f"Fecha: {record.create_date.strftime('%Y-%m-%d %H:%M') if record.create_date else 'N/A'}"
            )

            record.analysis_summary = "\n".join(summary_lines)

    def action_view_analysis(self):
        """Abre el análisis en el wizard para revisión"""
        return {
            "type": "ir.actions.act_window",
            "name": f"Revisar Análisis: {self.name}",
            "res_model": "tmdb.collection.analysis.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {
                "default_analysis_type": self.analysis_type,
                "default_date_from": self.date_from,
                "default_date_to": self.date_to,
                "default_min_rating": self.min_rating,
                "default_max_rating": self.max_rating,
                "default_min_popularity": self.min_popularity,
                "default_max_popularity": self.max_popularity,
                "default_total_movies": self.total_movies,
                "default_avg_rating": self.avg_rating,
                "default_avg_popularity": self.avg_popularity,
                "default_date_range": self.date_range,
                "default_decade_analysis": self.decade_analysis,
                "default_genre_analysis": self.genre_analysis,
                "default_rating_popularity_analysis": self.rating_popularity_analysis,
                "default_gaps_analysis": self.gaps_analysis,
                "default_decade_chart_data": self.decade_chart_data,
                "default_genre_chart_data": self.genre_chart_data,
                "default_rating_popularity_chart_data": self.rating_popularity_chart_data,
                "default_is_analysis_complete": True,
            },
        }

    def action_export_analysis(self):
        """Exporta el análisis a un archivo"""
        content = f"""
ANÁLISIS GUARDADO - {self.name}
================================
Fecha de Creación: {self.create_date}
Usuario: {self.user_id.name}
Tipo de Análisis: {dict(self._fields["analysis_type"].selection).get(self.analysis_type)}

ESTADÍSTICAS GENERALES
======================
Total de Películas: {self.total_movies}
Rating Promedio: {self.avg_rating:.2f}
Popularidad Promedio: {self.avg_popularity:.2f}
Rango de Fechas: {self.date_range}

FILTROS UTILIZADOS
==================
Fecha Desde: {self.date_from}
Fecha Hasta: {self.date_to}
Rating Mínimo: {self.min_rating}
Rating Máximo: {self.max_rating}
Popularidad Mínima: {self.min_popularity}
Popularidad Máxima: {self.max_popularity}

RESULTADOS DEL ANÁLISIS
========================

{self.decade_analysis}

{self.genre_analysis}

{self.rating_popularity_analysis}

{self.gaps_analysis}
        """

        # Crear archivo de descarga
        filename = (
            f"analisis_guardado_{self.id}_{self.create_date.strftime('%Y%m%d')}.txt"
        )

        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content?model=tmdb.permanent.analysis&id={self.id}&field=analysis_file&download=true&filename={filename}",
            "target": "self",
        }

    def action_compare_with_current(self):
        """Compara este análisis con el estado actual de la colección"""
        # Crear un nuevo wizard con los mismos filtros
        wizard = self.env["tmdb.collection.analysis.wizard"].create(
            {
                "analysis_type": self.analysis_type,
                "date_from": self.date_from,
                "date_to": self.date_to,
                "min_rating": self.min_rating,
                "max_rating": self.max_rating,
                "min_popularity": self.min_popularity,
                "max_popularity": self.max_popularity,
            }
        )

        # Ejecutar análisis
        wizard.action_run_analysis()

        return {
            "type": "ir.actions.act_window",
            "name": f"Comparar con Análisis Actual",
            "res_model": "tmdb.collection.analysis.wizard",
            "res_id": wizard.id,
            "view_mode": "form",
            "target": "new",
        }
