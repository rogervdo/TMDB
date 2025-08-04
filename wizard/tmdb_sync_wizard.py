from odoo import models, fields, api
from odoo.exceptions import UserError


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

    @api.onchange("sync_type")
    def _onchange_sync_type(self):
        """Clear fields based on sync type"""
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
