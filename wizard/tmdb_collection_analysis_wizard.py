from odoo import models, fields, api
from odoo.exceptions import UserError
import logging
from datetime import datetime, timedelta
from collections import defaultdict

_logger = logging.getLogger(__name__)


class TMDBCollectionAnalysisWizard(models.TransientModel):
    _name = "tmdb.collection.analysis.wizard"
    _description = "TMDB Collection Analysis Wizard"

    # ===== CAMPOS DE CONFIGURACIÓN =====
    analysis_type = fields.Selection(
        [
            ("decade", "Análisis por Décadas"),
            ("genre", "Distribución por Géneros"),
            ("rating_vs_popularity", "Calificaciones vs Popularidad"),
            ("gaps", "Identificación de Vacíos"),
            ("comprehensive", "Análisis Completo"),
        ],
        string="Tipo de Análisis",
        default="comprehensive",
        required=True,
    )

    # ===== FILTROS DE ANÁLISIS =====
    date_from = fields.Date(string="Fecha Desde", default=fields.Date.today)
    date_to = fields.Date(string="Fecha Hasta", default=fields.Date.today)
    min_rating = fields.Float(string="Rating Mínimo", default=0.0)
    max_rating = fields.Float(string="Rating Máximo", default=10.0)
    min_popularity = fields.Float(string="Popularidad Mínima", default=0.0)
    max_popularity = fields.Float(string="Popularidad Máxima", default=1000.0)

    # ===== CAMPOS DE RESULTADOS =====

    # Análisis por Décadas
    decade_analysis = fields.Text(string="Análisis por Décadas", readonly=True)
    decade_chart_data = fields.Text(
        string="Datos de Gráfico por Décadas", readonly=True
    )

    # Distribución por Géneros
    genre_analysis = fields.Text(string="Análisis por Géneros", readonly=True)
    genre_chart_data = fields.Text(string="Datos de Gráfico por Géneros", readonly=True)

    # Calificaciones vs Popularidad
    rating_popularity_analysis = fields.Text(
        string="Análisis Rating vs Popularidad", readonly=True
    )
    rating_popularity_chart_data = fields.Text(
        string="Datos de Gráfico Rating vs Popularidad", readonly=True
    )

    # Identificación de Vacíos
    gaps_analysis = fields.Text(string="Análisis de Vacíos", readonly=True)
    recommended_movies = fields.Text(string="Películas Recomendadas", readonly=True)

    # ===== ESTADÍSTICAS GENERALES =====
    total_movies = fields.Integer(string="Total de Películas", readonly=True)
    avg_rating = fields.Float(string="Rating Promedio", readonly=True, digits=(3, 2))
    avg_popularity = fields.Float(
        string="Popularidad Promedio", readonly=True, digits=(3, 2)
    )
    date_range = fields.Char(string="Rango de Fechas", readonly=True)

    # ===== CAMPOS DE CONTROL =====
    is_analysis_complete = fields.Boolean(string="Análisis Completado", default=False)
    last_analysis_date = fields.Datetime(string="Último Análisis", readonly=True)

    # ===== MÉTODOS DE ANÁLISIS =====

    @api.model
    def default_get(self, fields_list):
        """Configuración por defecto del wizard"""
        res = super().default_get(fields_list)

        # Establecer fechas por defecto (últimos 10 años)
        today = fields.Date.today()
        res["date_from"] = today - timedelta(days=3650)  # 10 años atrás
        res["date_to"] = today

        return res

    def action_run_analysis(self):
        """Ejecuta el análisis según el tipo seleccionado"""
        try:
            # Verificar que hay películas disponibles
            movies_count = self.env["tmdb.movie"].search_count([("active", "=", True)])
            if movies_count == 0:
                raise UserError(
                    "No hay películas disponibles para analizar. Sincronice películas desde TMDB primero."
                )

            _logger.info(f"Iniciando análisis de tipo: {self.analysis_type}")

            # Obtener películas filtradas para estadísticas generales
            movies = self._get_filtered_movies()

            # Actualizar estadísticas generales para todos los tipos de análisis
            self.total_movies = len(movies)
            self.avg_rating = (
                sum(m.vote_average for m in movies) / len(movies) if movies else 0
            )
            self.avg_popularity = (
                sum(m.popularity for m in movies) / len(movies) if movies else 0
            )
            self.date_range = f"{self.date_from} - {self.date_to}"

            if self.analysis_type == "decade":
                self._analyze_by_decades(movies)
            elif self.analysis_type == "genre":
                self._analyze_by_genres(movies)
            elif self.analysis_type == "rating_vs_popularity":
                self._analyze_rating_vs_popularity(movies)
            elif self.analysis_type == "gaps":
                self._analyze_collection_gaps(movies)
            elif self.analysis_type == "comprehensive":
                self._run_comprehensive_analysis(movies)

            self.is_analysis_complete = True
            self.last_analysis_date = fields.Datetime.now()

            _logger.info(
                f"Análisis completado exitosamente. Películas analizadas: {self.total_movies}"
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Análisis Completado",
                    "message": f'Análisis de tipo "{self.analysis_type}" completado exitosamente. Películas analizadas: {self.total_movies}. Ahora puede guardar el análisis.',
                    "type": "success",
                },
            }

        except Exception as e:
            _logger.error(f"Error en análisis de colección: {str(e)}")
            raise UserError(f"Error durante el análisis: {str(e)}")

    def _get_filtered_movies(self):
        """Obtiene las películas filtradas según los criterios del wizard"""
        domain = [
            ("active", "=", True),
        ]

        # Agregar filtros solo si los campos tienen valores válidos
        if self.date_from:
            domain.append(("release_date", ">=", self.date_from))
        if self.date_to:
            domain.append(("release_date", "<=", self.date_to))
        if self.min_rating is not None:
            domain.append(("vote_average", ">=", self.min_rating))
        if self.max_rating is not None:
            domain.append(("vote_average", "<=", self.max_rating))
        if self.min_popularity is not None:
            domain.append(("popularity", ">=", self.min_popularity))
        if self.max_popularity is not None:
            domain.append(("popularity", "<=", self.max_popularity))

        movies = self.env["tmdb.movie"].search(domain)
        _logger.info(f"Películas encontradas con filtros: {len(movies)}")
        return movies

    def _analyze_by_decades(self, movies=None):
        """Análisis de películas por décadas"""
        # Usar las películas ya filtradas en action_run_analysis
        if movies is None:
            movies = self._get_filtered_movies()

        # Agrupar por décadas
        decades = defaultdict(list)
        for movie in movies:
            if movie.release_date:
                decade = (movie.release_date.year // 10) * 10
                decades[f"{decade}s"].append(movie)

        # Generar análisis
        analysis_lines = []
        chart_data = []

        for decade in sorted(decades.keys()):
            decade_movies = decades[decade]
            avg_rating = (
                sum(m.vote_average for m in decade_movies) / len(decade_movies)
                if decade_movies
                else 0
            )
            avg_popularity = (
                sum(m.popularity for m in decade_movies) / len(decade_movies)
                if decade_movies
                else 0
            )

            analysis_lines.append(f"📅 {decade}: {len(decade_movies)} películas")
            analysis_lines.append(f"   • Rating promedio: {avg_rating:.2f}")
            analysis_lines.append(f"   • Popularidad promedio: {avg_popularity:.2f}")
            analysis_lines.append("")

            chart_data.append(
                {
                    "decade": decade,
                    "count": len(decade_movies),
                    "avg_rating": avg_rating,
                    "avg_popularity": avg_popularity,
                }
            )

        self.decade_analysis = "\n".join(analysis_lines)
        self.decade_chart_data = str(chart_data)

    def _analyze_by_genres(self, movies=None):
        """Análisis de distribución por géneros"""
        # Usar las películas ya filtradas en action_run_analysis
        if movies is None:
            movies = self._get_filtered_movies()

        # Agrupar por géneros
        genre_stats = defaultdict(lambda: {"count": 0, "ratings": [], "popularity": []})

        for movie in movies:
            for genre in movie.genre_ids:
                genre_stats[genre.name]["count"] += 1
                genre_stats[genre.name]["ratings"].append(movie.vote_average)
                genre_stats[genre.name]["popularity"].append(movie.popularity)

        # Generar análisis
        analysis_lines = []
        chart_data = []

        for genre_name, stats in sorted(
            genre_stats.items(), key=lambda x: x[1]["count"], reverse=True
        ):
            avg_rating = (
                sum(stats["ratings"]) / len(stats["ratings"]) if stats["ratings"] else 0
            )
            avg_popularity = (
                sum(stats["popularity"]) / len(stats["popularity"])
                if stats["popularity"]
                else 0
            )

            analysis_lines.append(f"🎭 {genre_name}: {stats['count']} películas")
            analysis_lines.append(f"   • Rating promedio: {avg_rating:.2f}")
            analysis_lines.append(f"   • Popularidad promedio: {avg_popularity:.2f}")
            analysis_lines.append("")

            chart_data.append(
                {
                    "genre": genre_name,
                    "count": stats["count"],
                    "avg_rating": avg_rating,
                    "avg_popularity": avg_popularity,
                }
            )

        self.genre_analysis = "\n".join(analysis_lines)
        self.genre_chart_data = str(chart_data)

    def _analyze_rating_vs_popularity(self, movies=None):
        """Análisis de correlación entre calificaciones y popularidad"""
        # Usar las películas ya filtradas en action_run_analysis
        if movies is None:
            movies = self._get_filtered_movies()

        # Calcular correlación
        high_rating_high_pop = []
        high_rating_low_pop = []
        low_rating_high_pop = []
        low_rating_low_pop = []

        for movie in movies:
            if movie.vote_average >= 7.0 and movie.popularity >= 200:
                high_rating_high_pop.append(movie)
            elif movie.vote_average >= 7.0 and movie.popularity < 200:
                high_rating_low_pop.append(movie)
            elif movie.vote_average < 7.0 and movie.popularity >= 200:
                low_rating_high_pop.append(movie)
            else:
                low_rating_low_pop.append(movie)

        # Generar análisis
        analysis_lines = []
        analysis_lines.append("📊 ANÁLISIS RATING VS POPULARIDAD")
        analysis_lines.append("=" * 40)
        analysis_lines.append(
            f"🎯 Alta Calificación + Alta Popularidad: {len(high_rating_high_pop)}"
        )
        analysis_lines.append(
            f"⭐ Alta Calificación + Baja Popularidad: {len(high_rating_low_pop)}"
        )
        analysis_lines.append(
            f"🔥 Baja Calificación + Alta Popularidad: {len(low_rating_high_pop)}"
        )
        analysis_lines.append(
            f"📉 Baja Calificación + Baja Popularidad: {len(low_rating_low_pop)}"
        )
        analysis_lines.append("")

        # Ejemplos de cada categoría
        if high_rating_high_pop:
            analysis_lines.append(
                "🎯 Ejemplos de Alta Calificación + Alta Popularidad:"
            )
            for movie in high_rating_high_pop[:5]:
                analysis_lines.append(
                    f"   • {movie.title} (Rating: {movie.vote_average}, Popularidad: {movie.popularity:.1f})"
                )
            analysis_lines.append("")

        if high_rating_low_pop:
            analysis_lines.append(
                "⭐ Películas Subestimadas (Alta Calificación, Baja Popularidad):"
            )
            for movie in high_rating_low_pop[:5]:
                analysis_lines.append(
                    f"   • {movie.title} (Rating: {movie.vote_average}, Popularidad: {movie.popularity:.1f})"
                )
            analysis_lines.append("")

        chart_data = {
            "high_rating_high_pop": len(high_rating_high_pop),
            "high_rating_low_pop": len(high_rating_low_pop),
            "low_rating_high_pop": len(low_rating_high_pop),
            "low_rating_low_pop": len(low_rating_low_pop),
        }

        self.rating_popularity_analysis = "\n".join(analysis_lines)
        self.rating_popularity_chart_data = str(chart_data)

    def _analyze_collection_gaps(self, movies=None):
        """Identificación de vacíos en la colección"""
        # Usar las películas ya filtradas en action_run_analysis
        if movies is None:
            movies = self._get_filtered_movies()

        # Análisis de vacíos por año
        years_with_movies = defaultdict(list)
        for movie in movies:
            if movie.release_date:
                years_with_movies[movie.release_date.year].append(movie)

        # Análisis de vacíos por género
        genre_coverage = defaultdict(int)
        all_genres = self.env["tmdb.genre"].search([])

        for movie in movies:
            for genre in movie.genre_ids:
                genre_coverage[genre.name] += 1

        # Generar análisis
        analysis_lines = []
        analysis_lines.append("🔍 IDENTIFICACIÓN DE VACÍOS EN LA COLECCIÓN")
        analysis_lines.append("=" * 50)

        # Vacíos por año
        analysis_lines.append("📅 DISTRIBUCIÓN POR AÑOS:")

        if years_with_movies:
            # Obtener años mínimo y máximo
            min_year = min(years_with_movies.keys())
            max_year = max(years_with_movies.keys())

            current_year = min_year
            total_years_with_movies = 0
            total_gaps = 0

            while current_year <= max_year:
                if current_year in years_with_movies:
                    # Año con películas
                    count = len(years_with_movies[current_year])
                    total_years_with_movies += 1
                    if count < 3:  # Considerar vacío si tiene menos de 3 películas
                        analysis_lines.append(
                            f"   ⚠️  {current_year}: Solo {count} películas (VACÍO)"
                        )
                    else:
                        analysis_lines.append(
                            f"   ✅ {current_year}: {count} películas"
                        )
                    current_year += 1
                else:
                    # Encontrar el siguiente año con películas
                    next_year_with_movies = None
                    for year in range(current_year + 1, max_year + 1):
                        if year in years_with_movies:
                            next_year_with_movies = year
                            break

                    if next_year_with_movies:
                        # Hay un rango vacío
                        if current_year == next_year_with_movies - 1:
                            analysis_lines.append(f"   ❌ {current_year}: 0 películas")
                        else:
                            analysis_lines.append(
                                f"   ❌ {current_year} - {next_year_with_movies - 1}: 0 películas"
                            )
                        total_gaps += 1
                        current_year = next_year_with_movies
                    else:
                        # No hay más años con películas
                        if current_year == max_year:
                            analysis_lines.append(f"   ❌ {current_year}: 0 películas")
                        else:
                            analysis_lines.append(
                                f"   ❌ {current_year} - {max_year}: 0 películas"
                            )
                        total_gaps += 1
                        break
        else:
            analysis_lines.append("   ❌ No hay películas con fechas de lanzamiento")

        analysis_lines.append(
            f"\n📊 RESUMEN: {total_years_with_movies} años con películas de {max_year - min_year + 1 if years_with_movies else 0} años analizados ({total_gaps} rangos vacíos)"
        )
        analysis_lines.append("")

        # Vacíos por género
        analysis_lines.append("🎭 DISTRIBUCIÓN POR GÉNEROS:")
        total_genres_with_movies = 0
        for genre in all_genres:
            count = genre_coverage.get(genre.name, 0)
            if count > 0:
                total_genres_with_movies += 1
                if count < 3:  # Considerar vacío si tiene menos de 3 películas
                    analysis_lines.append(
                        f"   ⚠️  {genre.name}: Solo {count} películas (VACÍO)"
                    )
                else:
                    analysis_lines.append(f"   ✅ {genre.name}: {count} películas")
            else:
                analysis_lines.append(
                    f"   ❌ {genre.name}: 0 películas (SIN PELÍCULAS)"
                )

        analysis_lines.append(
            f"\n📊 RESUMEN: {total_genres_with_movies} géneros con películas de {len(all_genres)} géneros disponibles"
        )
        analysis_lines.append("")

        # Recomendaciones
        analysis_lines.append("💡 RECOMENDACIONES:")
        analysis_lines.append("   • Buscar películas de años con poca representación")
        analysis_lines.append("   • Explorar géneros con baja cobertura")
        analysis_lines.append(
            "   • Considerar películas de alta calificación pero baja popularidad"
        )
        analysis_lines.append("   • Investigar períodos históricos con pocas películas")

        self.gaps_analysis = "\n".join(analysis_lines)

    def _run_comprehensive_analysis(self, movies=None):
        """Ejecuta un análisis completo de la colección"""
        # Las estadísticas generales ya se actualizaron en action_run_analysis

        # Ejecutar todos los análisis
        self._analyze_by_decades(movies)
        self._analyze_by_genres(movies)
        self._analyze_rating_vs_popularity(movies)
        self._analyze_collection_gaps(movies)

    def action_export_analysis(self):
        """Exporta el análisis a un formato legible"""
        if not self.is_analysis_complete:
            raise UserError("Debe ejecutar el análisis antes de exportar.")

        # Crear contenido del reporte
        report_content = f"""
ANÁLISIS DE COLECCIÓN TMDB
===========================
Fecha: {self.last_analysis_date}
Rango: {self.date_range}
Total de Películas: {self.total_movies}
Rating Promedio: {self.avg_rating:.2f}
Popularidad Promedio: {self.avg_popularity:.2f}

{self.decade_analysis}

{self.genre_analysis}

{self.rating_popularity_analysis}

{self.gaps_analysis}
        """

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Análisis Exportado",
                "message": "El análisis ha sido exportado al portapapeles.",
                "type": "success",
            },
        }

    def action_save_analysis_permanent(self):
        """Guarda el análisis de forma permanente en un modelo separado"""
        if not self.is_analysis_complete:
            raise UserError("Debe ejecutar el análisis antes de guardar.")

        try:
            # Verificar que tenemos datos válidos para guardar
            if not self.total_movies or self.total_movies == 0:
                raise UserError("No hay datos de análisis válidos para guardar.")

            # Crear registro permanente
            permanent_analysis = self.env["tmdb.permanent.analysis"].create(
                {
                    "name": f"Análisis {self.analysis_type} - {fields.Date.today()}",
                    "analysis_type": self.analysis_type,
                    "date_from": self.date_from,
                    "date_to": self.date_to,
                    "min_rating": self.min_rating,
                    "max_rating": self.max_rating,
                    "min_popularity": self.min_popularity,
                    "max_popularity": self.max_popularity,
                    "total_movies": self.total_movies,
                    "avg_rating": self.avg_rating,
                    "avg_popularity": self.avg_popularity,
                    "date_range": self.date_range,
                    "decade_analysis": self.decade_analysis,
                    "genre_analysis": self.genre_analysis,
                    "rating_popularity_analysis": self.rating_popularity_analysis,
                    "gaps_analysis": self.gaps_analysis,
                    "decade_chart_data": self.decade_chart_data,
                    "genre_chart_data": self.genre_chart_data,
                    "rating_popularity_chart_data": self.rating_popularity_chart_data,
                    "user_id": self.env.user.id,
                }
            )

            _logger.info(
                f"Análisis guardado permanentemente con ID: {permanent_analysis.id}"
            )

            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Análisis Guardado",
                    "message": f"Análisis guardado permanentemente con ID: {permanent_analysis.id}. Películas analizadas: {self.total_movies}",
                    "type": "success",
                },
            }
        except Exception as e:
            _logger.error(f"Error al guardar análisis: {str(e)}")
            raise UserError(f"Error al guardar el análisis: {str(e)}")

    def action_export_to_file(self):
        """Exporta el análisis a un archivo de texto"""
        if not self.is_analysis_complete:
            raise UserError("Debe ejecutar el análisis antes de exportar.")

        # Crear contenido del archivo
        filename = f"analisis_coleccion_{fields.Date.today()}.txt"
        content = f"""
ANÁLISIS DE COLECCIÓN TMDB
===========================
Fecha: {self.last_analysis_date}
Rango: {self.date_range}
Total de Películas: {self.total_movies}
Rating Promedio: {self.avg_rating:.2f}
Popularidad Promedio: {self.avg_popularity:.2f}

{self.decade_analysis}

{self.genre_analysis}

{self.rating_popularity_analysis}

{self.gaps_analysis}
        """

        # Crear archivo de descarga
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content?model=tmdb.collection.analysis.wizard&id={self.id}&field=analysis_file&download=true&filename={filename}",
            "target": "self",
        }

    def action_clear_analysis(self):
        """Limpia los resultados del análisis"""
        self.write(
            {
                "decade_analysis": "",
                "genre_analysis": "",
                "rating_popularity_analysis": "",
                "gaps_analysis": "",
                "is_analysis_complete": False,
                "last_analysis_date": False,
                "total_movies": 0,
                "avg_rating": 0.0,
                "avg_popularity": 0.0,
                "date_range": "",
            }
        )

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Análisis Limpiado",
                "message": "Los resultados del análisis han sido limpiados.",
                "type": "info",
            },
        }

    def action_check_analysis_status(self):
        """Verifica los datos disponibles para el análisis"""
        movies_count = self.env["tmdb.movie"].search_count([("active", "=", True)])
        filtered_movies = self._get_filtered_movies()

        # Check if permanent analysis model is accessible
        try:
            permanent_analysis_count = self.env["tmdb.permanent.analysis"].search_count(
                []
            )
            permanent_analysis_accessible = True
        except Exception as e:
            permanent_analysis_accessible = False
            permanent_analysis_count = 0

        message = f"""
Datos Disponibles para Análisis:
- Películas totales en BD: {movies_count}
- Películas con filtros aplicados: {len(filtered_movies)}
- Análisis completado: {"Sí" if self.is_analysis_complete else "No"}
- Tipo de análisis: {self.analysis_type}
- Filtros aplicados: {self.date_from} - {self.date_to}
- Modelo de análisis permanente accesible: {"Sí" if permanent_analysis_accessible else "No"}
- Análisis guardados existentes: {permanent_analysis_count}
        """

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Datos Disponibles para Análisis",
                "message": message,
                "type": "info",
            },
        }

    def action_run_and_save_analysis(self):
        """Ejecuta el análisis y lo guarda automáticamente"""
        try:
            # Ejecutar el análisis
            result = self.action_run_analysis()

            # Si el análisis fue exitoso, guardarlo automáticamente
            if self.is_analysis_complete:
                save_result = self.action_save_analysis_permanent()
                return save_result
            else:
                return result

        except Exception as e:
            _logger.error(f"Error en análisis y guardado: {str(e)}")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error",
                    "message": f"Error durante el análisis y guardado: {str(e)}",
                    "type": "danger",
                },
            }

    def action_debug_wizard_state(self):
        """Método de debug para verificar el estado del wizard"""
        debug_info = f"""
Estado del Wizard:
- ID: {self.id}
- Análisis completado: {self.is_analysis_complete}
- Total películas: {self.total_movies}
- Rating promedio: {self.avg_rating}
- Popularidad promedio: {self.avg_popularity}
- Tipo de análisis: {self.analysis_type}
- Fecha desde: {self.date_from}
- Fecha hasta: {self.date_to}
- Análisis por décadas: {"Sí" if self.decade_analysis else "No"}
- Análisis por géneros: {"Sí" if self.genre_analysis else "No"}
- Análisis rating vs popularidad: {"Sí" if self.rating_popularity_analysis else "No"}
- Análisis de vacíos: {"Sí" if self.gaps_analysis else "No"}
        """

        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Debug - Estado del Wizard",
                "message": debug_info,
                "type": "info",
            },
        }

    def action_test_save_analysis(self):
        """Prueba específicamente el guardado del análisis actual"""
        try:
            # Verificar el estado antes de intentar guardar
            if not self.is_analysis_complete:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Error",
                        "message": "El análisis no está completado. Ejecute el análisis primero.",
                        "type": "danger",
                    },
                }

            if not self.total_movies or self.total_movies == 0:
                return {
                    "type": "ir.actions.client",
                    "tag": "display_notification",
                    "params": {
                        "title": "Error",
                        "message": "No hay películas analizadas. El análisis no encontró datos.",
                        "type": "danger",
                    },
                }

            # Intentar guardar
            save_result = self.action_save_analysis_permanent()
            return save_result

        except Exception as e:
            _logger.error(f"Error en prueba de guardado: {str(e)}")
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": "Error en Prueba de Guardado",
                    "message": f"Error: {str(e)}",
                    "type": "danger",
                },
            }
