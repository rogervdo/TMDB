from odoo import models, fields, api
from odoo.exceptions import UserError, ValidationError
import logging
from datetime import timedelta
from collections import defaultdict

_logger = logging.getLogger(__name__)


class TMDBCollectionAnalysisWizard(models.TransientModel):
    _name = "tmdb.collection.analysis.wizard"
    _description = "TMDB Collection Analysis Wizard"

    # ===== CONSTANTS =====
    ANALYSIS_TYPES = [
        ("decade", "Análisis por Décadas"),
        ("genre", "Distribución por Géneros"),
        ("rating_vs_popularity", "Calificaciones vs Popularidad"),
        ("gaps", "Identificación de Vacíos"),
        ("comprehensive", "Análisis Completo"),
    ]

    HIGH_RATING_THRESHOLD = 7.0
    HIGH_POPULARITY_THRESHOLD = 200.0
    MINIMAL_MOVIE_THRESHOLD = 3
    DEFAULT_YEARS_BACK = 10 * 365  # 10 years in days

    # ===== FIELDS =====

    # Configuration fields
    analysis_type = fields.Selection(
        ANALYSIS_TYPES,
        string="Tipo de Análisis",
        default="comprehensive",
        required=True,
    )

    # Filter fields
    date_from = fields.Date(string="Fecha Desde", default=fields.Date.today)
    date_to = fields.Date(string="Fecha Hasta", default=fields.Date.today)
    min_rating = fields.Float(string="Rating Mínimo", default=0.0)
    max_rating = fields.Float(string="Rating Máximo", default=10.0)
    min_popularity = fields.Float(string="Popularidad Mínima", default=0.0)
    max_popularity = fields.Float(string="Popularidad Máxima", default=1000.0)

    # Result fields - Decade Analysis
    decade_analysis = fields.Text(string="Análisis por Décadas", readonly=True)
    decade_chart_data = fields.Text(
        string="Datos de Gráfico por Décadas", readonly=True
    )

    # Result fields - Genre Distribution
    genre_analysis = fields.Text(string="Análisis por Géneros", readonly=True)
    genre_chart_data = fields.Text(string="Datos de Gráfico por Géneros", readonly=True)

    # Result fields - Rating vs Popularity
    rating_popularity_analysis = fields.Text(
        string="Análisis Rating vs Popularidad", readonly=True
    )
    rating_popularity_chart_data = fields.Text(
        string="Datos de Gráfico Rating vs Popularidad", readonly=True
    )

    # Result fields - Collection Gaps
    gaps_analysis = fields.Text(string="Análisis de Vacíos", readonly=True)
    recommended_movies = fields.Text(string="Películas Recomendadas", readonly=True)

    # General statistics
    total_movies = fields.Integer(string="Total de Películas", readonly=True)
    avg_rating = fields.Float(string="Rating Promedio", readonly=True, digits=(3, 2))
    avg_popularity = fields.Float(
        string="Popularidad Promedio", readonly=True, digits=(3, 2)
    )
    date_range = fields.Char(string="Rango de Fechas", readonly=True)

    # Control fields
    is_analysis_complete = fields.Boolean(string="Análisis Completado", default=False)
    last_analysis_date = fields.Datetime(string="Último Análisis", readonly=True)

    # ===== CONSTRAINTS =====

    @api.constrains("date_from", "date_to")
    def _check_date_range(self):
        """Validate that date_from is not after date_to"""
        for record in self:
            if (
                record.date_from
                and record.date_to
                and record.date_from > record.date_to
            ):
                raise ValidationError(
                    "La fecha desde no puede ser posterior a la fecha hasta"
                )

    @api.constrains("min_rating", "max_rating")
    def _check_rating_range(self):
        """Validate rating range is valid"""
        for record in self:
            if record.min_rating < 0 or record.max_rating > 10:
                raise ValidationError("El rating debe estar entre 0 y 10")
            if record.min_rating > record.max_rating:
                raise ValidationError(
                    "El rating mínimo no puede ser mayor que el rating máximo"
                )

    @api.constrains("min_popularity", "max_popularity")
    def _check_popularity_range(self):
        """Validate popularity range is valid"""
        for record in self:
            if record.min_popularity < 0:
                raise ValidationError("La popularidad no puede ser negativa")
            if record.min_popularity > record.max_popularity:
                raise ValidationError(
                    "La popularidad mínima no puede ser mayor que la popularidad máxima"
                )

    # ===== DEFAULT VALUES =====

    @api.model
    def default_get(self, fields_list):
        """Set default configuration for the wizard"""
        res = super().default_get(fields_list)

        # Set default dates (last 10 years)
        today = fields.Date.today()
        res["date_from"] = today - timedelta(days=self.DEFAULT_YEARS_BACK)
        res["date_to"] = today

        return res

    # ===== MAIN ANALYSIS METHODS =====

    def action_run_analysis(self):
        """Execute analysis according to selected type"""
        try:
            # Verify movies are available
            movies_count = self.env["tmdb.movie"].search_count([("active", "=", True)])
            if movies_count == 0:
                raise UserError(
                    "No movies available for analysis. Please sync movies from TMDB first."
                )

            _logger.info(f"Starting analysis of type: {self.analysis_type}")

            # Get filtered movies for general statistics
            movies = self._get_filtered_movies()

            # Update general statistics for all analysis types
            self._update_general_statistics(movies)

            # Execute specific analysis based on type
            analysis_methods = {
                "decade": self._analyze_by_decades,
                "genre": self._analyze_by_genres,
                "rating_vs_popularity": self._analyze_rating_vs_popularity,
                "gaps": self._analyze_collection_gaps,
                "comprehensive": self._run_comprehensive_analysis,
            }

            analysis_method = analysis_methods.get(self.analysis_type)
            if analysis_method:
                analysis_method(movies)

            self.is_analysis_complete = True
            self.last_analysis_date = fields.Datetime.now()

            _logger.info(
                f"Analysis completed successfully. Movies analyzed: {self.total_movies}"
            )

            return self._get_success_notification(
                "Analysis Complete",
                f'Analysis type "{self.analysis_type}" completed successfully. '
                f"Movies analyzed: {self.total_movies}. You can now save the analysis.",
            )

        except Exception as e:
            _logger.error(f"Error in collection analysis: {str(e)}")
            raise UserError(f"Error during analysis: {str(e)}")

    def _get_filtered_movies(self):
        """Get movies filtered according to wizard criteria"""
        domain = [("active", "=", True)]

        # Add filters only if fields have valid values
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
        _logger.info(f"Movies found with filters: {len(movies)}")
        return movies

    def _update_general_statistics(self, movies):
        """Update general statistics for all analysis types"""
        self.total_movies = len(movies)
        self.avg_rating = self._calculate_average_rating(movies)
        self.avg_popularity = self._calculate_average_popularity(movies)
        self.date_range = f"{self.date_from} - {self.date_to}"

    def _calculate_average_rating(self, movies):
        """Calculate average rating from movie recordset"""
        if not movies:
            return 0.0
        total_rating = sum(movie.vote_average for movie in movies)
        return round(total_rating / len(movies), 2)

    def _calculate_average_popularity(self, movies):
        """Calculate average popularity from movie recordset"""
        if not movies:
            return 0.0
        total_popularity = sum(movie.popularity for movie in movies)
        return round(total_popularity / len(movies), 2)

    def _calculate_average_from_list(self, values):
        """Calculate average from a list of numeric values"""
        if not values:
            return 0.0
        return round(sum(values) / len(values), 2)

    def _get_success_notification(self, title, message):
        """Generate success notification action"""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": "success",
            },
        }

    def _get_error_notification(self, title, message):
        """Generate error notification action"""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": "danger",
            },
        }

    def _get_info_notification(self, title, message):
        """Generate info notification action"""
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": title,
                "message": message,
                "type": "info",
            },
        }

    # ===== SPECIFIC ANALYSIS METHODS =====

    def _analyze_by_decades(self, movies=None):
        """Analyze movies by decades"""
        if movies is None:
            movies = self._get_filtered_movies()

        # Group by decades
        decades = defaultdict(list)
        for movie in movies:
            if movie.release_date:
                decade = (movie.release_date.year // 10) * 10
                decades[f"{decade}s"].append(movie)

        # Generate analysis
        analysis_lines = []
        chart_data = []

        for decade in sorted(decades.keys()):
            decade_movies = decades[decade]
            avg_rating = self._calculate_average_rating(decade_movies)
            avg_popularity = self._calculate_average_popularity(decade_movies)

            analysis_lines.append(f"📅 {decade}: {len(decade_movies)} movies")
            analysis_lines.append(f"   • Average rating: {avg_rating:.2f}")
            analysis_lines.append(f"   • Average popularity: {avg_popularity:.2f}")
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
        """Analyze distribution by genres"""
        if movies is None:
            movies = self._get_filtered_movies()

        # Group by genres
        genre_stats = defaultdict(lambda: {"count": 0, "ratings": [], "popularity": []})

        for movie in movies:
            for genre in movie.genre_ids:
                genre_stats[genre.name]["count"] += 1
                genre_stats[genre.name]["ratings"].append(movie.vote_average)
                genre_stats[genre.name]["popularity"].append(movie.popularity)

        # Generate analysis
        analysis_lines = []
        chart_data = []

        for genre_name, stats in sorted(
            genre_stats.items(), key=lambda x: x[1]["count"], reverse=True
        ):
            avg_rating = self._calculate_average_from_list(stats["ratings"])
            avg_popularity = self._calculate_average_from_list(stats["popularity"])

            analysis_lines.append(f"🎭 {genre_name}: {stats['count']} movies")
            analysis_lines.append(f"   • Average rating: {avg_rating:.2f}")
            analysis_lines.append(f"   • Average popularity: {avg_popularity:.2f}")
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
        """Analyze correlation between rating and popularity"""
        if movies is None:
            movies = self._get_filtered_movies()

        # Categorize movies
        categories = self._categorize_movies_by_rating_and_popularity(movies)

        # Generate analysis
        analysis_lines = []
        analysis_lines.append("📊 RATING VS POPULARITY ANALYSIS")
        analysis_lines.append("=" * 40)
        analysis_lines.append(
            f"🎯 High Rating + High Popularity: {len(categories['high_rating_high_pop'])}"
        )
        analysis_lines.append(
            f"⭐ High Rating + Low Popularity: {len(categories['high_rating_low_pop'])}"
        )
        analysis_lines.append(
            f"🔥 Low Rating + High Popularity: {len(categories['low_rating_high_pop'])}"
        )
        analysis_lines.append(
            f"📉 Low Rating + Low Popularity: {len(categories['low_rating_low_pop'])}"
        )
        analysis_lines.append("")

        # Add examples from each category
        self._add_category_examples(analysis_lines, categories)

        chart_data = {
            "high_rating_high_pop": len(categories["high_rating_high_pop"]),
            "high_rating_low_pop": len(categories["high_rating_low_pop"]),
            "low_rating_high_pop": len(categories["low_rating_high_pop"]),
            "low_rating_low_pop": len(categories["low_rating_low_pop"]),
        }

        self.rating_popularity_analysis = "\n".join(analysis_lines)
        self.rating_popularity_chart_data = str(chart_data)

    def _categorize_movies_by_rating_and_popularity(self, movies):
        """Categorize movies by rating and popularity thresholds"""
        categories = {
            "high_rating_high_pop": [],
            "high_rating_low_pop": [],
            "low_rating_high_pop": [],
            "low_rating_low_pop": [],
        }

        for movie in movies:
            is_high_rating = movie.vote_average >= self.HIGH_RATING_THRESHOLD
            is_high_popularity = movie.popularity >= self.HIGH_POPULARITY_THRESHOLD

            if is_high_rating and is_high_popularity:
                categories["high_rating_high_pop"].append(movie)
            elif is_high_rating and not is_high_popularity:
                categories["high_rating_low_pop"].append(movie)
            elif not is_high_rating and is_high_popularity:
                categories["low_rating_high_pop"].append(movie)
            else:
                categories["low_rating_low_pop"].append(movie)

        return categories

    def _add_category_examples(self, analysis_lines, categories):
        """Add example movies from each category to analysis"""
        if categories["high_rating_high_pop"]:
            analysis_lines.append("🎯 Examples of High Rating + High Popularity:")
            for movie in categories["high_rating_high_pop"][:5]:
                analysis_lines.append(
                    f"   • {movie.title} (Rating: {movie.vote_average}, Popularity: {movie.popularity:.1f})"
                )
            analysis_lines.append("")

        if categories["high_rating_low_pop"]:
            analysis_lines.append("⭐ Underrated Movies (High Rating, Low Popularity):")
            for movie in categories["high_rating_low_pop"][:5]:
                analysis_lines.append(
                    f"   • {movie.title} (Rating: {movie.vote_average}, Popularity: {movie.popularity:.1f})"
                )
            analysis_lines.append("")

    def _analyze_collection_gaps(self, movies=None):
        """Identify gaps in the collection"""
        if movies is None:
            movies = self._get_filtered_movies()

        # Analyze gaps by year
        years_with_movies = self._group_movies_by_year(movies)

        # Analyze gaps by genre
        genre_coverage = self._analyze_genre_coverage(movies)

        # Generate analysis
        analysis_lines = []
        analysis_lines.append("🔍 COLLECTION GAPS IDENTIFICATION")
        analysis_lines.append("=" * 50)

        # Add year analysis
        self._add_year_gap_analysis(analysis_lines, years_with_movies)

        # Add genre analysis
        self._add_genre_gap_analysis(analysis_lines, genre_coverage)

        # Add recommendations
        self._add_gap_recommendations(analysis_lines)

        self.gaps_analysis = "\n".join(analysis_lines)

    def _group_movies_by_year(self, movies):
        """Group movies by release year"""
        years_with_movies = defaultdict(list)
        for movie in movies:
            if movie.release_date:
                years_with_movies[movie.release_date.year].append(movie)
        return years_with_movies

    def _analyze_genre_coverage(self, movies):
        """Analyze genre coverage in the collection"""
        genre_coverage = defaultdict(int)
        for movie in movies:
            for genre in movie.genre_ids:
                genre_coverage[genre.name] += 1
        return genre_coverage

    def _add_year_gap_analysis(self, analysis_lines, years_with_movies):
        """Add year gap analysis to the report"""
        analysis_lines.append("📅 DISTRIBUTION BY YEARS:")

        if not years_with_movies:
            analysis_lines.append("   ❌ No movies with release dates")
            return

        min_year = min(years_with_movies.keys())
        max_year = max(years_with_movies.keys())
        total_years_with_movies, total_gaps = self._analyze_year_gaps(
            analysis_lines, years_with_movies, min_year, max_year
        )

        analysis_lines.append(
            f"\n📊 SUMMARY: {total_years_with_movies} years with movies out of "
            f"{max_year - min_year + 1} analyzed years ({total_gaps} gap ranges)"
        )
        analysis_lines.append("")

    def _analyze_year_gaps(self, analysis_lines, years_with_movies, min_year, max_year):
        """Analyze gaps in years and add to analysis"""
        total_years_with_movies = 0
        total_gaps = 0
        current_year = min_year

        while current_year <= max_year:
            if current_year in years_with_movies:
                count = len(years_with_movies[current_year])
                total_years_with_movies += 1
                if count < self.MINIMAL_MOVIE_THRESHOLD:
                    analysis_lines.append(
                        f"   ⚠️  {current_year}: Only {count} movies (GAP)"
                    )
                else:
                    analysis_lines.append(f"   ✅ {current_year}: {count} movies")
                current_year += 1
            else:
                current_year, gap_added = self._handle_year_gap(
                    analysis_lines, years_with_movies, current_year, max_year
                )
                if gap_added:
                    total_gaps += 1

        return total_years_with_movies, total_gaps

    def _handle_year_gap(
        self, analysis_lines, years_with_movies, current_year, max_year
    ):
        """Handle a gap in years and return next year to process"""
        next_year_with_movies = None
        for year in range(current_year + 1, max_year + 1):
            if year in years_with_movies:
                next_year_with_movies = year
                break

        if next_year_with_movies:
            if current_year == next_year_with_movies - 1:
                analysis_lines.append(f"   ❌ {current_year}: 0 movies")
            else:
                analysis_lines.append(
                    f"   ❌ {current_year} - {next_year_with_movies - 1}: 0 movies"
                )
            return next_year_with_movies, True
        else:
            if current_year == max_year:
                analysis_lines.append(f"   ❌ {current_year}: 0 movies")
            else:
                analysis_lines.append(f"   ❌ {current_year} - {max_year}: 0 movies")
            return max_year + 1, True

    def _add_genre_gap_analysis(self, analysis_lines, genre_coverage):
        """Add genre gap analysis to the report"""
        analysis_lines.append("🎭 DISTRIBUTION BY GENRES:")
        all_genres = self.env["tmdb.genre"].search([])
        total_genres_with_movies = 0

        for genre in all_genres:
            count = genre_coverage.get(genre.name, 0)
            if count > 0:
                total_genres_with_movies += 1
                if count < self.MINIMAL_MOVIE_THRESHOLD:
                    analysis_lines.append(
                        f"   ⚠️  {genre.name}: Only {count} movies (GAP)"
                    )
                else:
                    analysis_lines.append(f"   ✅ {genre.name}: {count} movies")
            else:
                analysis_lines.append(f"   ❌ {genre.name}: 0 movies (NO MOVIES)")

        analysis_lines.append(
            f"\n📊 SUMMARY: {total_genres_with_movies} genres with movies out of "
            f"{len(all_genres)} available genres"
        )
        analysis_lines.append("")

    def _add_gap_recommendations(self, analysis_lines):
        """Add recommendations to fill collection gaps"""
        analysis_lines.append("💡 RECOMMENDATIONS:")
        analysis_lines.append("   • Search for movies from underrepresented years")
        analysis_lines.append("   • Explore genres with low coverage")
        analysis_lines.append("   • Consider high-rated but low-popularity movies")
        analysis_lines.append("   • Research historical periods with few movies")

    def _run_comprehensive_analysis(self, movies=None):
        """Execute comprehensive analysis of the collection"""
        # General statistics already updated in action_run_analysis

        # Execute all analysis types
        self._analyze_by_decades(movies)
        self._analyze_by_genres(movies)
        self._analyze_rating_vs_popularity(movies)
        self._analyze_collection_gaps(movies)

    # ===== ACTION METHODS =====

    def action_export_analysis(self):
        """Export analysis to readable format"""
        if not self.is_analysis_complete:
            raise UserError("Must execute analysis before exporting.")

        return self._get_success_notification(
            "Analysis Exported", "Analysis has been exported to clipboard."
        )

    def action_save_analysis_permanent(self):
        """Save analysis permanently in a separate model"""
        if not self.is_analysis_complete:
            raise UserError("Must execute analysis before saving.")

        try:
            # Verify we have valid data to save
            if not self.total_movies or self.total_movies == 0:
                raise UserError("No valid analysis data to save.")

            # Create permanent record
            permanent_analysis = self.env["tmdb.permanent.analysis"].create(
                self._prepare_permanent_analysis_values()
            )

            _logger.info(f"Analysis saved permanently with ID: {permanent_analysis.id}")

            return self._get_success_notification(
                "Analysis Saved",
                f"Analysis saved permanently with ID: {permanent_analysis.id}. "
                f"Movies analyzed: {self.total_movies}",
            )

        except Exception as e:
            _logger.error(f"Error saving analysis: {str(e)}")
            raise UserError(f"Error saving analysis: {str(e)}")

    def _prepare_permanent_analysis_values(self):
        """Prepare values for permanent analysis record"""
        return {
            "name": f"Analysis {self.analysis_type} - {fields.Date.today()}",
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

    def action_export_to_file(self):
        """Export analysis to text file"""
        if not self.is_analysis_complete:
            raise UserError("Must execute analysis before exporting.")

        # Create download file
        filename = f"collection_analysis_{fields.Date.today()}.txt"
        return {
            "type": "ir.actions.act_url",
            "url": f"/web/content?model=tmdb.collection.analysis.wizard&id={self.id}&field=analysis_file&download=true&filename={filename}",
            "target": "self",
        }

    def action_clear_analysis(self):
        """Clear analysis results"""
        self.write(self._get_clear_analysis_values())
        return self._get_info_notification(
            "Analysis Cleared", "Analysis results have been cleared."
        )

    def _get_clear_analysis_values(self):
        """Get values to clear all analysis fields"""
        return {
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

    def action_check_analysis_status(self):
        """Check available data for analysis"""
        movies_count = self.env["tmdb.movie"].search_count([("active", "=", True)])
        filtered_movies = self._get_filtered_movies()

        # Check if permanent analysis model is accessible
        permanent_analysis_accessible, permanent_analysis_count = (
            self._check_permanent_analysis_access()
        )

        message = self._build_status_message(
            movies_count,
            filtered_movies,
            permanent_analysis_accessible,
            permanent_analysis_count,
        )

        return self._get_info_notification("Available Data for Analysis", message)

    def _check_permanent_analysis_access(self):
        """Check if permanent analysis model is accessible"""
        try:
            count = self.env["tmdb.permanent.analysis"].search_count([])
            return True, count
        except Exception:
            return False, 0

    def _build_status_message(
        self, movies_count, filtered_movies, permanent_accessible, permanent_count
    ):
        """Build status message for analysis data"""
        return f"""
Available Data for Analysis:
- Total movies in DB: {movies_count}
- Movies with applied filters: {len(filtered_movies)}
- Analysis completed: {"Yes" if self.is_analysis_complete else "No"}
- Analysis type: {self.analysis_type}
- Applied filters: {self.date_from} - {self.date_to}
- Permanent analysis model accessible: {"Yes" if permanent_accessible else "No"}
- Existing saved analyses: {permanent_count}
        """

    def action_run_and_save_analysis(self):
        """Execute analysis and save it automatically"""
        try:
            # Execute analysis
            result = self.action_run_analysis()

            # If analysis was successful, save it automatically
            if self.is_analysis_complete:
                return self.action_save_analysis_permanent()
            else:
                return result

        except Exception as e:
            _logger.error(f"Error in analysis and save: {str(e)}")
            return self._get_error_notification(
                "Error", f"Error during analysis and save: {str(e)}"
            )
