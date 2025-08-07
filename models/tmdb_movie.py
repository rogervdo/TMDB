from odoo import models, fields, api
from odoo.exceptions import ValidationError
import requests
import logging

_logger = logging.getLogger(__name__)


class TMDBMovie(models.Model):
    _name = "tmdb.movie"
    _description = "TMDB Movie"
    _order = "title"
    _inherit = ["tmdb.utils", "tmdb.utils.contact"]

    # ===== SQL CONSTRAINTS =====
    _sql_constraints = [
        ("tmdb_id_unique", "unique(tmdb_id)", "TMDB ID must be unique"),
    ]

    # ===== FIELDS =====

    # Basic movie information
    tmdb_id = fields.Integer(string="TMDB ID", required=True)
    title = fields.Char(string="Title", required=True)
    original_title = fields.Char(string="Original Title")
    overview = fields.Text(string="Overview")
    release_date = fields.Date(string="Release Date")

    # Movie metrics and metadata
    popularity = fields.Float(string="Popularity")
    vote_average = fields.Float(string="Vote Average")
    vote_count = fields.Integer(string="Vote Count")
    poster_path = fields.Char(string="Poster Path")
    backdrop_path = fields.Char(string="Backdrop Path")
    director = fields.Char(string="Director", help="Main director of the movie")

    # Relationships
    genre_ids = fields.Many2many(
        "tmdb.genre",
        string="Genres",
        help="Genres that belong to this movie",
    )

    director_id = fields.Many2one(
        "res.partner",
        string="Director Contact",
        help="Link to director contact in Odoo contacts",
        domain="[('is_company', '=', False)]",
    )

    actor_ids = fields.Many2many(
        "res.partner",  # Modelo Relacionado
        "movie_actor_rel",  # Nombre de la tabla intermedia
        "movie_id",  # Campo para este modelo
        "actor_id",  # Campo para el otro modelo
        string="Actores",
        domain="[('is_actor', '=', True)]",  # Solo mostrar contactos ACTORES
    )

    # Computed fields
    recommendation_score = fields.Float(
        string="Recommendation Score",
        compute="_compute_recommendation_score",
        store=True,
    )

    age_category = fields.Selection(
        [("Clasica", "Clasica"), ("Reciente", "Reciente"), ("Nueva", "Nueva")],
        string="Age Category",
        compute="_compute_age_category",
        store=True,
    )

    popularity_category = fields.Selection(
        [("Viral", "Viral"), ("Alta", "Alta"), ("Media", "Media"), ("Baja", "Baja")],
        string="Popularity Category",
        compute="_compute_popularity_category",
        store=True,
    )

    total_actors = fields.Integer(
        string="Total de Actores", compute="_compute_total_actors"
    )

    # Status fields
    active = fields.Boolean(string="Active", default=True)
    last_sync = fields.Datetime(string="Last Sync", default=fields.Datetime.now)

    # ===== SYNC METHODS =====

    # XML Action
    def sync_from_tmdb(self):
        """Button action to sync this movie from TMDB"""
        if not self.tmdb_id:
            return self.get_notification(
                "Error", "No TMDB ID specified for this movie.", "danger"
            )

        try:
            updated_movie = self.sync_movie_from_tmdb(self.tmdb_id)
            if updated_movie:
                return self.get_notification(
                    "Success",
                    f'Movie "{self.title}" successfully synced from TMDB.',
                    "success",
                )
            else:
                return self.get_notification(
                    "Error",
                    "Failed to sync movie from TMDB. Please check your API key and connection.",
                    "danger",
                )
        except Exception as e:
            _logger.error(f"Error syncing movie {self.tmdb_id}: {e}")
            return self.get_notification(
                "Error", f"An error occurred while syncing: {str(e)}", "danger"
            )

    def fetch_movie_from_tmdb(self, tmdb_id):
        """Fetch movie data from TMDB API"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/movie/{tmdb_id}"
        params = {"api_key": api_key, "language": "en-US"}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching movie {tmdb_id}: {e}")
            return None

    def sync_movie_from_tmdb(self, tmdb_id):
        """Sync movie data from TMDB to local database"""
        movie_data = self.fetch_movie_from_tmdb(tmdb_id)
        if not movie_data:
            return False

        existing_movie = self.search([("tmdb_id", "=", tmdb_id)])

        # Process director information
        director, director_contact = self._process_director_info(tmdb_id)

        # Process actors information
        actor_ids = self._process_actors_info(tmdb_id)

        # Process genres
        genre_ids = self._process_genres(movie_data.get("genres", []))

        movie_vals = self._prepare_movie_values(
            movie_data, director, director_contact, genre_ids, actor_ids
        )

        if existing_movie:
            existing_movie.write(movie_vals)
            return existing_movie
        else:
            return self.create(movie_vals)

    def _process_actors_info(self, tmdb_id):
        """Process actors information from TMDB and return actor IDs"""
        try:
            credits_data = self.fetch_movie_credits_from_tmdb(tmdb_id)
            if not credits_data or "cast" not in credits_data:
                return []

            actor_ids = []
            # Sort cast by popularity and take top 5 actors
            cast_members = credits_data.get("cast", [])
            # Sort by popularity (descending) and take top 5
            sorted_cast = sorted(
                cast_members, key=lambda x: x.get("popularity", 0), reverse=True
            )[:5]

            for cast_member in sorted_cast:
                actor_name = cast_member.get("name")
                profile_path = cast_member.get("profile_path")
                if actor_name:
                    # Find or create actor contact with profile image
                    actor_contact = self.find_or_create_actor_contact(
                        actor_name, profile_path
                    )
                    if actor_contact:
                        actor_ids.append(actor_contact.id)

            return actor_ids
        except Exception as e:
            _logger.error(f"Error processing actors for TMDB ID {tmdb_id}: {e}")
            return []

    def sync_popular_movies(self, page=1, limit=20, year_filter=None):
        """Sync popular movies from TMDB with optional year filtering"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url, params = self._build_popular_movies_url(
            api_key, base_url, page, year_filter
        )

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            synced_count = 0
            for movie in data.get("results", [])[:limit]:
                if self.sync_movie_from_tmdb(movie.get("id")):
                    synced_count += 1

            return synced_count

        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching popular movies: {e}")
            return 0

    def find_or_create_actor_contact(self, actor_name, profile_path=None):
        if not actor_name:
            return None

        # Buscar actor existente
        existing_actor = self.env["res.partner"].search(
            [("name", "=", actor_name), ("is_actor", "=", True)], limit=1
        )

        if existing_actor:
            # Update image if we have a profile_path and the contact doesn't have an image yet
            if profile_path and not existing_actor.image_1920:
                existing_actor.update_image_from_tmdb_profile(profile_path)
            return existing_actor

        # Crear nuevo actor
        try:
            actor_vals = {
                "name": actor_name,
                "is_company": False,
                "is_actor": True,
                "function": "Actor",
            }
            new_actor = self.env["res.partner"].create(actor_vals)

            # Add profile image if available
            if profile_path:
                new_actor.update_image_from_tmdb_profile(profile_path)

            return new_actor
        except Exception as e:
            _logger.error(f"Error creating actor contact for {actor_name}: {e}")
            return None

    def fetch_movie_credits_from_tmdb(self, tmdb_id):
        """Fetch movie credits data from TMDB API"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/movie/{tmdb_id}/credits"
        params = {"api_key": api_key, "language": "en-US"}

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error fetching movie credits {tmdb_id}: {e}")
            return None

    def get_director_from_credits(self, credits_data):
        """Extract director name and profile path from credits data"""
        if not credits_data or "crew" not in credits_data:
            return None, None

        for crew_member in credits_data["crew"]:
            if crew_member.get("job") == "Director":
                return crew_member.get("name"), crew_member.get("profile_path")

        return None, None

    def update_director_from_tmdb(self):
        """Update director information for this movie from TMDB"""
        if not self.tmdb_id:
            return self.get_notification(
                "Error", "No TMDB ID specified for this movie.", "danger"
            )

        try:
            credits_data = self.fetch_movie_credits_from_tmdb(self.tmdb_id)
            if credits_data:
                director, director_profile_path = self.get_director_from_credits(
                    credits_data
                )
                if director:
                    director_contact = self.find_or_create_director_contact_simple(
                        director, director_profile_path
                    )
                    self.write(
                        {
                            "director": director,
                            "director_id": director_contact.id
                            if director_contact
                            else False,
                        }
                    )
                    return self.get_notification(
                        "Success", f"Director updated: {director}", "success"
                    )
                else:
                    return self.get_notification(
                        "Info", "No director information found for this movie.", "info"
                    )
            else:
                return self.get_notification(
                    "Error", "Failed to fetch credits from TMDB.", "danger"
                )
        except Exception as e:
            _logger.error(f"Error updating director for movie {self.tmdb_id}: {e}")
            return self.get_notification(
                "Error",
                f"An error occurred while updating director: {str(e)}",
                "danger",
            )

    def sync_all_contacts(self):
        """Sync all directors and actors from movies to contacts"""
        # Get all movies to sync
        all_movies = self.search([])

        # Sync directors
        director_count = super().sync_all_directors_to_contacts(all_movies)

        # Sync actors
        actor_count = self._sync_all_actors_to_contacts(all_movies)

        total_count = director_count + actor_count
        return self.get_notification(
            "Success",
            f"Synced {director_count} directors and {actor_count} actors to contacts ({total_count} total).",
            "success",
        )

    def _sync_all_actors_to_contacts(self, movie_records):
        """Sync all actors from movies to contacts"""
        synced_count = 0

        for movie in movie_records:
            try:
                # Process actors for this movie if it has TMDB ID
                if movie.tmdb_id:
                    actor_ids = self._process_actors_info(movie.tmdb_id)
                    if actor_ids:
                        movie.write({"actor_ids": [(6, 0, actor_ids)]})
                        synced_count += len(actor_ids)
            except Exception as e:
                _logger.error(f"Error syncing actors for movie {movie.title}: {e}")

        return synced_count

    def create_director_contact_from_field(self):
        """Create director contact from the director field"""
        return super().create_director_contactExp_from_field(self)

    # ===== SEARCH METHODS =====

    def search_movies(self, query, page=1, year_filter=None):
        """Search movies on TMDB with optional year filtering"""
        api_key = self.get_tmdb_api_key()
        base_url = self.get_tmdb_base_url()

        if not api_key:
            raise ValueError("TMDB API key not configured")

        url = f"{base_url}/search/movie"
        params = {"api_key": api_key, "language": "en-US", "query": query, "page": page}

        if year_filter:
            start_date = f"{year_filter}-01-01"
            end_date = f"{year_filter}-12-31"
            params["primary_release_date.gte"] = start_date
            params["primary_release_date.lte"] = end_date

        try:
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            _logger.error(f"Error searching movies: {e}")
            return None

    @api.model
    def get_available_genres_for_filter(self):
        """Get available genres for dynamic filtering"""
        genres = self.env["tmdb.genre"].search([])
        return [{"id": genre.id, "name": genre.name} for genre in genres]

    @api.model
    def search_by_genre(self, genre_name):
        """Search movies by specific genre"""
        return self.search([("genre_ids.name", "=", genre_name)])

    @api.model
    def search_by_rating_range(self, min_rating, max_rating=None):
        """Search movies by rating range"""
        domain = [("vote_average", ">=", min_rating)]
        if max_rating:
            domain.append(("vote_average", "<=", max_rating))
        return self.search(domain)

    @api.model
    def search_by_popularity(self, min_popularity):
        """Search movies by minimum popularity"""
        return self.search([("popularity", ">=", min_popularity)])

    @api.model
    def search_by_year_range(self, start_year, end_year=None):
        """Search movies by year range"""
        start_date = f"{start_year}-01-01"
        if end_year:
            end_date = f"{end_year}-12-31"
            domain = [
                ("release_date", ">=", start_date),
                ("release_date", "<=", end_date),
            ]
        else:
            domain = [("release_date", ">=", start_date)]
        return self.search(domain)

    # ===== CONSTRAINTS =====

    @api.constrains("release_date")
    def validate_date(self):
        for record in self:
            if record.release_date and record.release_date > fields.Date.today():
                raise ValidationError(
                    f"Release date cannot be in the future: {record.title} in {record.release_date}"
                )

    @api.constrains("vote_average")
    def validate_vote_average(self):
        for record in self:
            if record.vote_average < 0 or record.vote_average > 10:
                raise ValidationError(
                    f"Vote average must be between 0 and 10: {record.title} in {record.vote_average}"
                )

    @api.constrains("vote_count")
    def validate_vote_count(self):
        for record in self:
            if record.vote_count < 0:
                raise ValidationError(
                    f"Vote count must be greater than 0: {record.title} in {record.vote_count}"
                )

    @api.constrains("tmdb_id")
    def validate_unique_tmdb_id(self):
        for record in self:
            if self.search_count([("tmdb_id", "=", record.tmdb_id)]) > 1:
                raise ValidationError(
                    f"TMDB ID must be unique: {record.title} in {record.tmdb_id}"
                )

    # ===== COMPUTED FIELDS =====

    @api.depends("actor_ids")
    def _compute_total_actors(self):
        for movie in self:
            movie.total_actors = len(movie.actor_ids)

    @api.depends("release_date")
    def _compute_age_category(self):
        for record in self:
            category = False
            if record.release_date:
                today = fields.Date.today()
                age = (
                    (today - record.release_date).days // 365
                    if today >= record.release_date
                    else 0
                )
                if age >= 30:
                    category = "Clasica"
                elif 5 < age < 30:
                    category = "Reciente"
                elif age <= 5:
                    category = "Nueva"
            record.age_category = category

    @api.depends("popularity")
    def _compute_popularity_category(self):
        for record in self:
            category = False
            if record.popularity:
                if record.popularity > 500:
                    category = "Viral"
                elif record.popularity > 250:
                    category = "Alta"
                elif record.popularity > 150:
                    category = "Media"
                else:
                    category = "Baja"
            record.popularity_category = category

    @api.depends("popularity", "vote_average")
    def _compute_recommendation_score(self):
        for record in self:
            if record.popularity and record.vote_average:
                record.recommendation_score = (
                    record.popularity + record.vote_average * 100
                ) / 100
            else:
                record.recommendation_score = 0
            record.recommendation_score = round(record.recommendation_score, 2)

    # ===== PRIVATE HELPER METHODS =====

    def _process_director_info(self, tmdb_id):
        """Process director information from TMDB credits"""
        director = None
        director_contact = None
        credits_data = self.fetch_movie_credits_from_tmdb(tmdb_id)
        if credits_data:
            director, director_profile_path = self.get_director_from_credits(
                credits_data
            )
            if director:
                director_contact = self.find_or_create_director_contact_simple(
                    director, director_profile_path
                )
        return director, director_contact

    def _process_genres(self, genres_data):
        """Process genres data and return genre IDs"""
        genre_ids = []
        if genres_data:
            for genre in genres_data:
                genre_record = self.env["tmdb.genre"].search(
                    [("tmdb_genre_id", "=", genre["id"])]
                )
                if genre_record:
                    genre_ids.append(genre_record.id)
                else:
                    genre_record = self.env["tmdb.genre"].create(
                        {"tmdb_genre_id": genre["id"], "name": genre["name"]}
                    )
                    genre_ids.append(genre_record.id)
        return genre_ids

    def _prepare_movie_values(
        self, movie_data, director, director_contact, genre_ids, actor_ids=None
    ):
        """Prepare movie values for create/update operations"""
        movie_vals = {
            "tmdb_id": movie_data.get("id"),
            "title": movie_data.get("title") or "",
            "original_title": movie_data.get("original_title") or False,
            "overview": movie_data.get("overview") or False,
            "release_date": movie_data.get("release_date") or False,
            "popularity": movie_data.get("popularity") or 0.0,
            "vote_average": movie_data.get("vote_average") or 0.0,
            "vote_count": movie_data.get("vote_count") or 0,
            "poster_path": movie_data.get("poster_path") or False,
            "backdrop_path": movie_data.get("backdrop_path") or False,
            "director": director or False,
            "director_id": director_contact.id if director_contact else False,
            "last_sync": fields.Datetime.now(),
            "genre_ids": [(6, 0, genre_ids)],
        }

        # Add actor_ids if provided
        if actor_ids:
            movie_vals["actor_ids"] = [(6, 0, actor_ids)]

        return movie_vals

    def _build_popular_movies_url(self, api_key, base_url, page, year_filter):
        """Build URL and parameters for popular movies API call"""
        if year_filter:
            url = f"{base_url}/discover/movie"
            start_date = f"{year_filter}-01-01"
            end_date = f"{year_filter}-12-31"
            params = {
                "api_key": api_key,
                "language": "en-US",
                "page": page,
                "sort_by": "popularity.desc",
                "primary_release_date.gte": start_date,
                "primary_release_date.lte": end_date,
            }
        else:
            url = f"{base_url}/movie/popular"
            params = {"api_key": api_key, "language": "en-US", "page": page}

        return url, params
