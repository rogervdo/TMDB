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

    def action_sync_movies(self):
        """Execute the sync operation based on selected type"""
        movie_model = self.env["tmdb.movie"]

        if self.sync_type == "popular":
            synced_count = movie_model.sync_popular_movies(
                page=self.page, limit=self.limit
            )
            message = f"Successfully synced {synced_count} popular movies from TMDB."

        elif self.sync_type == "search":
            if not self.search_query:
                raise UserError("Please enter a search query.")

            search_results = movie_model.search_movies(
                query=self.search_query, page=self.page
            )

            if not search_results or not search_results.get("results"):
                raise UserError("No movies found for the search query.")

            synced_count = 0
            for movie in search_results["results"][: self.limit]:
                if movie_model.sync_movie_from_tmdb(movie.get("id")):
                    synced_count += 1

            message = f"Successfully synced {synced_count} movies from search results."

        elif self.sync_type == "specific":
            if not self.movie_id:
                raise UserError("Please enter a TMDB Movie ID.")

            movie = movie_model.sync_movie_from_tmdb(self.movie_id)
            if movie:
                message = f"Successfully synced movie: {movie.title}"
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
