from odoo import models, fields, api
from odoo.exceptions import UserError
import json
import logging

_logger = logging.getLogger(__name__)


class TMDBMovieSyncWizard(models.TransientModel):
    _name = "tmdb.movie.sync.wizard"
    _description = "TMDB Movie Sync Wizard"

    sync_type = fields.Selection(
        [
            ("popular", "Popular Movies"),
            ("search", "Search Movies"),
            ("specific", "Specific Movie ID"),
            ("genres_first", "Sync Genres First, Then Movies"),
        ],
        string="Sync Type",
        required=True,
        default="popular",
    )

    search_query = fields.Char(
        string="Search Query", help="Enter movie title to search"
    )

    movie_id = fields.Integer(
        string="TMDB Movie ID", help="Enter specific TMDB movie ID"
    )

    limit = fields.Integer(string="Limit", default=20, help="Number of movies to sync")

    page = fields.Integer(string="Page", default=1, help="Page number for pagination")

    # New field for year filtering
    year_filter = fields.Integer(
        string="Year Filter", help="Filter movies by specific year (optional)"
    )

    sync_genres_first = fields.Boolean(
        string="Sync Genres Before Movies",
        default=True,
        help="Sync all available genres from TMDB before syncing movies",
    )

    # New field for selective genre syncing
    sync_only_new_genres = fields.Boolean(
        string="Sync Only New Genres",
        default=False,
        help="Only sync genres that don't already exist in the database",
    )

    # Wizard state management
    wizard_step = fields.Selection(
        [
            ("configure", "Configuration"),
            ("preview", "Preview"),
            ("complete", "Complete"),
        ],
        string="Wizard Step",
        default="configure",
    )

    # Preview data fields
    preview_data = fields.Text(
        string="Preview Data",
        help="JSON data containing movies to be synced (for preview)",
    )

    preview_movies_count = fields.Integer(
        string="Movies to Sync",
        compute="_compute_preview_counts",
        help="Number of movies that will be synced",
    )

    preview_new_movies_count = fields.Integer(
        string="New Movies",
        compute="_compute_preview_counts",
        help="Number of new movies that will be created",
    )

    preview_existing_movies_count = fields.Integer(
        string="Existing Movies",
        compute="_compute_preview_counts",
        help="Number of existing movies that will be updated",
    )

    preview_genres_count = fields.Integer(
        string="Genres to Sync",
        help="Number of genres that will be synced",
    )

    preview_movies_list = fields.Html(
        string="Movies List",
        compute="_compute_preview_movies_list",
        help="Formatted list of movies to be synced",
    )

    @api.depends("preview_data")
    def _compute_preview_counts(self):
        """Compute preview counts from preview data"""
        for record in self:
            if record.preview_data:
                try:
                    preview_info = json.loads(record.preview_data)
                    movies_data = preview_info.get("movies", [])

                    record.preview_movies_count = len(movies_data)

                    # Count new vs existing movies
                    new_count = 0
                    existing_count = 0

                    for movie_data in movies_data:
                        tmdb_id = movie_data.get("id")
                        if tmdb_id:
                            existing = self.env["tmdb.movie"].search_count(
                                [("tmdb_id", "=", tmdb_id)]
                            )
                            if existing:
                                existing_count += 1
                            else:
                                new_count += 1

                    record.preview_new_movies_count = new_count
                    record.preview_existing_movies_count = existing_count

                except (ValueError, TypeError):
                    record.preview_movies_count = 0
                    record.preview_new_movies_count = 0
                    record.preview_existing_movies_count = 0
            else:
                record.preview_movies_count = 0
                record.preview_new_movies_count = 0
                record.preview_existing_movies_count = 0

    @api.depends("preview_data")
    def _compute_preview_movies_list(self):
        """Compute formatted movies list for preview"""
        for record in self:
            if record.preview_data:
                try:
                    preview_info = json.loads(record.preview_data)
                    movies_data = preview_info.get("movies", [])

                    if movies_data:
                        html_content = "<div class='o_form_field_html'><ul style='margin: 0; padding-left: 20px;'>"

                        for movie in movies_data[:10]:  # Show first 10 movies
                            title = movie.get("title", "Unknown Title")
                            release_date = movie.get("release_date", "Unknown")
                            tmdb_id = movie.get("id", "Unknown")

                            # Check if movie exists
                            existing = self.env["tmdb.movie"].search_count(
                                [("tmdb_id", "=", tmdb_id)]
                            )
                            status = "⟳ Update" if existing else "✓ New"
                            status_class = (
                                "text-warning" if existing else "text-success"
                            )

                            html_content += f"""
                                <li style='margin-bottom: 8px;'>
                                    <strong>{title}</strong> ({release_date})
                                    <br/>
                                    <small>TMDB ID: {tmdb_id} | 
                                    <span class='{status_class}'>{status}</span></small>
                                </li>
                            """

                        if len(movies_data) > 10:
                            html_content += f"<li><em>... and {len(movies_data) - 10} more movies</em></li>"

                        html_content += "</ul></div>"
                        record.preview_movies_list = html_content
                    else:
                        record.preview_movies_list = "<p>No movies found.</p>"

                except (ValueError, TypeError):
                    record.preview_movies_list = "<p>Error loading movie data.</p>"
            else:
                record.preview_movies_list = ""

    @api.onchange("sync_type")
    def _onchange_sync_type(self):
        """Clear fields based on sync type"""
        # Reset wizard step and preview data
        self.wizard_step = "configure"
        self.preview_data = False
        self.preview_genres_count = 0

        if self.sync_type == "popular":
            self.search_query = False
            self.movie_id = False
        elif self.sync_type == "search":
            self.movie_id = False
        elif self.sync_type == "specific":
            self.search_query = False
            self.limit = 1
        elif self.sync_type == "genres_first":
            self.search_query = False
            self.movie_id = False

    def action_preview_sync(self):
        """Generate preview of what will be synced"""
        movie_model = self.env["tmdb.movie"]
        preview_info = {"movies": [], "genres_count": 0}

        try:
            # Get genres count if needed
            if self.sync_genres_first and self.sync_type != "genres_first":
                # Estimate genres based on sync type
                genre_data = self._get_genres_data_from_tmdb()
                if genre_data:
                    if self.sync_only_new_genres:
                        existing_genres = movie_model.env["tmdb.genre"].search_count([])
                        self.preview_genres_count = (
                            len(genre_data) - existing_genres
                            if len(genre_data) > existing_genres
                            else 0
                        )
                    else:
                        self.preview_genres_count = len(genre_data)
                    preview_info["genres_count"] = self.preview_genres_count

            # Get movie data based on sync type
            if self.sync_type == "genres_first":
                # Only genres to sync
                genre_data = self._get_genres_data_from_tmdb()
                if genre_data:
                    if self.sync_only_new_genres:
                        existing_genres = movie_model.env["tmdb.genre"].search_count([])
                        self.preview_genres_count = (
                            len(genre_data) - existing_genres
                            if len(genre_data) > existing_genres
                            else 0
                        )
                    else:
                        self.preview_genres_count = len(genre_data)
                    preview_info["genres_count"] = self.preview_genres_count

            elif self.sync_type == "popular":
                # Get popular movies data without syncing
                api_key = movie_model.get_tmdb_api_key()
                base_url = movie_model.get_tmdb_base_url()

                if self.year_filter:
                    url = f"{base_url}/discover/movie"
                    start_date = f"{self.year_filter}-01-01"
                    end_date = f"{self.year_filter}-12-31"
                    params = {
                        "api_key": api_key,
                        "language": "en-US",
                        "page": self.page,
                        "sort_by": "popularity.desc",
                        "primary_release_date.gte": start_date,
                        "primary_release_date.lte": end_date,
                    }
                else:
                    url = f"{base_url}/movie/popular"
                    params = {
                        "api_key": api_key,
                        "language": "en-US",
                        "page": self.page,
                    }

                import requests

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                preview_info["movies"] = data.get("results", [])[: self.limit]

            elif self.sync_type == "search":
                if not self.search_query:
                    raise UserError("Please enter a search query.")

                search_results = movie_model.search_movies(
                    query=self.search_query,
                    page=self.page,
                    year_filter=self.year_filter,
                )

                if not search_results or not search_results.get("results"):
                    raise UserError("No movies found for the search query.")

                preview_info["movies"] = search_results["results"][: self.limit]

            elif self.sync_type == "specific":
                if not self.movie_id:
                    raise UserError("Please enter a TMDB Movie ID.")

                movie_data = movie_model.fetch_movie_from_tmdb(self.movie_id)
                if movie_data:
                    preview_info["movies"] = [movie_data]
                else:
                    raise UserError(f"Movie with ID {self.movie_id} not found.")

            # Store preview data as JSON
            self.preview_data = json.dumps(preview_info)
            self.wizard_step = "preview"

        except Exception as e:
            raise UserError(f"Error generating preview: {str(e)}")

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def action_back_to_configure(self):
        """Go back to configuration step"""
        self.wizard_step = "configure"
        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }

    def _get_genres_data_from_tmdb(self):
        """Get genres data from TMDB without syncing"""
        try:
            movie_model = self.env["tmdb.movie"]
            api_key = movie_model.get_tmdb_api_key()
            base_url = movie_model.get_tmdb_base_url()

            if not api_key:
                return []

            url = f"{base_url}/genre/movie/list"
            params = {"api_key": api_key, "language": "en-US"}

            import requests

            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            return data.get("genres", [])

        except Exception as e:
            _logger.error(f"Error getting genres data from TMDB: {e}")
            return []

    def sync_genres_from_tmdb(self):
        """Sync genres from TMDB with option to sync only new ones"""
        if self.sync_only_new_genres:
            return self.env["tmdb.genre"].sync_only_new_genres_from_tmdb()
        else:
            return self.env["tmdb.genre"].sync_all_genres_from_tmdb()

    def action_sync_movies(self):
        """Execute the sync operation based on selected type"""
        movie_model = self.env["tmdb.movie"]

        # Sync genres first if requested
        genre_sync_result = None
        if self.sync_genres_first and self.sync_type != "genres_first":
            genre_sync_result = self.sync_genres_from_tmdb()

        if self.sync_type == "genres_first":
            # Only sync genres
            genre_sync_result = self.sync_genres_from_tmdb()
            message = f"Successfully synced {genre_sync_result['total']} genres from TMDB ({genre_sync_result['created']} created, {genre_sync_result['synced']} updated)."

        elif self.sync_type == "popular":
            synced_count = movie_model.sync_popular_movies(
                page=self.page, limit=self.limit, year_filter=self.year_filter
            )
            message = f"Successfully synced {synced_count} popular movies from TMDB."
            if self.year_filter:
                message += f" Filtered by year: {self.year_filter}"
            if genre_sync_result:
                message += f" Also synced {genre_sync_result['total']} genres."

        elif self.sync_type == "search":
            if not self.search_query:
                raise UserError("Please enter a search query.")

            search_results = movie_model.search_movies(
                query=self.search_query, page=self.page, year_filter=self.year_filter
            )

            if not search_results or not search_results.get("results"):
                raise UserError("No movies found for the search query.")

            synced_count = 0

            for i, movie in enumerate(search_results["results"][: self.limit]):
                if movie_model.sync_movie_from_tmdb(movie.get("id")):
                    synced_count += 1

            message = f"Successfully synced {synced_count} movies from search results."
            if self.year_filter:
                message += f" Filtered by year: {self.year_filter}"
            if genre_sync_result:
                message += f" Also synced {genre_sync_result['total']} genres."

        elif self.sync_type == "specific":
            if not self.movie_id:
                raise UserError("Please enter a TMDB Movie ID.")

            movie = movie_model.sync_movie_from_tmdb(self.movie_id)
            if movie:
                message = f"Successfully synced movie: {movie.title}"
                if genre_sync_result:
                    message += f" Also synced {genre_sync_result['total']} genres."
            else:
                raise UserError(f"Failed to sync movie with ID {self.movie_id}")

        # Mark wizard as complete
        self.wizard_step = "complete"

        # Show success message
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": "Sync Complete",
                "message": message,
                "type": "success",
                "sticky": False,
            },
        }

    def action_close_wizard(self):
        """Close the wizard"""
        return {"type": "ir.actions.act_window_close"}
