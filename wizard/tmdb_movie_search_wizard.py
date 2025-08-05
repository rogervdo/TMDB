from odoo import models, fields, api
from odoo.exceptions import UserError


class TMDBMovieSearchWizard(models.TransientModel):
    _name = "tmdb.movie.search.wizard"
    _description = "TMDB Movie Search Wizard"

    search_query = fields.Char(string="Search Query")
    limit = fields.Integer(
        string="Total Results",
        default=100,
        help="Maximum number of results to fetch from TMDB (will automatically fetch multiple pages)",
    )
    page = fields.Integer(string="Page", default=1)
    genre = fields.Many2one(
        "tmdb.genre",
        string="Genre",
        help="Select a genre to filter movies by",
    )
    minscore = fields.Float(string="Min Score", digits=(3, 1))
    maxscore = fields.Float(string="Max Score", digits=(3, 1))
    minpopularity = fields.Integer(string="Min Popularity")
    maxpopularity = fields.Integer(string="Max Popularity")
    minyear = fields.Integer(string="Min Year")
    maxyear = fields.Integer(string="Max Year")

    # TOGGLES
    filter_year = fields.Boolean(string="Filter Year", default=False)
    filter_genre = fields.Boolean(string="Filter Genre", default=False)
    filter_score = fields.Boolean(string="Filter Score", default=False)
    filter_popularity = fields.Boolean(string="Filter Popularity", default=False)

    #! CONSTRAINTS
    @api.constrains("minscore", "maxscore")
    def _check_score_range(self):
        for record in self:
            if record.filter_score:  # Solo validar si el filtro está activo
                if record.minscore and record.maxscore:
                    if record.minscore > record.maxscore:
                        raise UserError("Min score must be less than max score")
                    if record.minscore < 0 or record.maxscore > 10:
                        raise UserError("Score must be between 0 and 10")
                elif record.minscore and (record.minscore < 0 or record.minscore > 10):
                    raise UserError("Min score must be between 0 and 10")
                elif record.maxscore and (record.maxscore < 0 or record.maxscore > 10):
                    raise UserError("Max score must be between 0 and 10")

    @api.constrains("minpopularity", "maxpopularity")
    def _check_popularity_range(self):
        for record in self:
            if record.filter_popularity:  # Solo validar si el filtro está activo
                if record.minpopularity and record.maxpopularity:
                    if record.minpopularity > record.maxpopularity:
                        raise UserError(
                            "Min popularity must be less than max popularity"
                        )
                    if record.minpopularity < 0 or record.maxpopularity < 0:
                        raise UserError("Popularity must be positive")
                elif record.minpopularity and record.minpopularity < 0:
                    raise UserError("Min popularity must be positive")
                elif record.maxpopularity and record.maxpopularity < 0:
                    raise UserError("Max popularity must be positive")

    @api.constrains("minyear", "maxyear")
    def _check_year_range(self):
        for record in self:
            if record.filter_year:  # Solo validar si el filtro está activo
                if record.minyear and record.maxyear:
                    if record.minyear > record.maxyear:
                        raise UserError("Min year must be less than max year")
                    if record.minyear < 1900 or record.maxyear > 2030:
                        raise UserError("Year must be between 1900 and 2030")
                elif record.minyear and (
                    record.minyear < 1900 or record.minyear > 2030
                ):
                    raise UserError("Min year must be between 1900 and 2030")
                elif record.maxyear and (
                    record.maxyear < 1900 or record.maxyear > 2030
                ):
                    raise UserError("Max year must be between 1900 and 2030")

    @api.constrains("limit")
    def _check_limit(self):
        for record in self:
            if record.limit and (record.limit < 1 or record.limit > 1000):
                raise UserError("Total results must be between 1 and 1000")

    def _build_score_domain(self):
        domain = []

        if not self.filter_score:
            return domain

        if self.minscore:
            domain.append(("vote_average", ">=", self.minscore))

        if self.maxscore:
            domain.append(("vote_average", "<=", self.maxscore))

        return domain

    def _build_popularity_domain(self):
        domain = []

        if not self.filter_popularity:
            return domain

        if self.minpopularity:
            domain.append(("popularity", ">=", self.minpopularity))

        if self.maxpopularity:
            domain.append(("popularity", "<=", self.maxpopularity))

        return domain

    def _build_year_domain(self):
        domain = []

        if not self.filter_year:
            return domain

        if self.minyear:
            domain.append(("release_date", ">=", f"{self.minyear}-01-01"))

        if self.maxyear:
            domain.append(("release_date", "<=", f"{self.maxyear}-12-31"))

        return domain

    def _build_genre_domain(self):
        domain = []

        if not self.filter_genre or not self.genre:
            return domain

        domain.append(("genre_ids", "in", [self.genre.id]))
        return domain

    def _build_search_query_domain(self):
        domain = []

        if not self.search_query:
            return domain

        domain.append(("title", "ilike", self.search_query))
        return domain

    def search_local_movies(self):
        """Busca películas en la base de datos local usando todos los filtros"""
        domain = []

        # Combinar todos los dominios
        domain.extend(self._build_search_query_domain())
        domain.extend(self._build_genre_domain())
        domain.extend(self._build_score_domain())
        domain.extend(self._build_popularity_domain())
        domain.extend(self._build_year_domain())

        # Si no hay ningún filtro activo, mostrar todas las películas
        if not any(
            [
                self.search_query,
                self.filter_genre and self.genre,
                self.filter_score and (self.minscore or self.maxscore),
                self.filter_popularity and (self.minpopularity or self.maxpopularity),
                self.filter_year and (self.minyear or self.maxyear),
            ]
        ):
            domain = [("active", "=", True)]  # Solo películas activas

        # Ejecutar la búsqueda
        movies = self.env["tmdb.movie"].search(domain, limit=self.limit)

        # Retornar vista de resultados
        return {
            "type": "ir.actions.act_window",
            "res_model": "tmdb.movie",
            "view_mode": "list,form",
            "domain": [("id", "in", movies.ids)],
            "name": f"Resultados de búsqueda local ({len(movies)} películas)",
            "target": "current",
        }

    def search_tmdb_movies(self):
        """Busca películas en TMDB usando el endpoint Discover con paginación automática"""
        movie_model = self.env["tmdb.movie"]
        api_key = movie_model.get_tmdb_api_key()
        base_url = movie_model.get_tmdb_base_url()

        if not api_key:
            raise UserError("TMDB API key not configured")

        all_movies_data = []
        current_page = 1
        max_pages = 50  # Limitar a 50 páginas para evitar bucles infinitos
        total_available = 0

        while len(all_movies_data) < self.limit and current_page <= max_pages:
            # Decidir endpoint basado en si hay query de texto
            if self.search_query:
                # Para búsqueda por texto, usar search endpoint
                url = f"{base_url}/search/movie"
                params = {
                    "api_key": api_key,
                    "language": "en-US",
                    "query": self.search_query,
                    "page": current_page,
                }
            else:
                # Para filtros avanzados, usar discover endpoint
                url = f"{base_url}/discover/movie"
                params = {
                    "api_key": api_key,
                    "language": "en-US",
                    "page": current_page,
                    "sort_by": "popularity.desc",  # Ordenar por popularidad por defecto
                }

            # Mapear filtros del wizard a parámetros TMDB
            self._add_tmdb_filters(params)

            try:
                import requests

                response = requests.get(url, params=params, timeout=10)
                response.raise_for_status()
                data = response.json()

                movies_data = data.get("results", [])
                total_available = data.get("total_results", 0)

                if not movies_data:
                    # No hay más resultados en esta página
                    break

                # Aplicar filtros que TMDB no soporta directamente (popularidad)
                filtered_movies = self._apply_client_side_filters(movies_data)

                all_movies_data.extend(filtered_movies)

                # Si hemos alcanzado el total de páginas disponibles, parar
                total_pages = data.get("total_pages", 1)
                if current_page >= total_pages:
                    break

                current_page += 1

            except requests.exceptions.RequestException as e:
                if current_page == 1:
                    # Si es el primer error, lanzar la excepción
                    raise UserError(f"Error searching TMDB: {str(e)}")
                else:
                    # Si hay error en páginas posteriores, usar lo que tenemos
                    break
            except Exception as e:
                if current_page == 1:
                    raise UserError(f"An error occurred: {str(e)}")
                else:
                    break

        # Aplicar el límite final
        final_movies_data = all_movies_data[: self.limit]

        if not final_movies_data:
            raise UserError("No movies found with the specified criteria.")

        # Mostrar resultados
        return self._show_tmdb_results(final_movies_data, total_available)

    def _add_tmdb_filters(self, params):
        """Mapea los filtros del wizard a parámetros TMDB"""

        # Filtros de fecha/año → primary_release_date
        if self.filter_year:
            if self.minyear:
                params["primary_release_date.gte"] = f"{self.minyear}-01-01"
            if self.maxyear:
                params["primary_release_date.lte"] = f"{self.maxyear}-12-31"

        # Filtros de score → vote_average
        if self.filter_score:
            if self.minscore:
                params["vote_average.gte"] = self.minscore
            if self.maxscore:
                params["vote_average.lte"] = self.maxscore

        # Filtros de género → with_genres
        if self.filter_genre and self.genre:
            params["with_genres"] = self.genre.tmdb_genre_id

        # Nota: Popularidad se filtra del lado cliente porque TMDB no tiene min/max popularity

    def _apply_client_side_filters(self, movies_data):
        """Aplica filtros que TMDB no soporta directamente"""

        if not self.filter_popularity:
            return movies_data

        filtered_movies = []
        for movie in movies_data:
            popularity = movie.get("popularity", 0.0)

            # Verificar filtro mínimo de popularidad
            if self.minpopularity and popularity < self.minpopularity:
                continue

            # Verificar filtro máximo de popularidad
            if self.maxpopularity and popularity > self.maxpopularity:
                continue

            filtered_movies.append(movie)

        return filtered_movies

    def _show_tmdb_results(self, movies_data, total_results):
        """Muestra los resultados de TMDB en una vista tree profesional"""

        # Crear registros transient con los resultados
        result_model = self.env["tmdb.search.result"]
        result_ids = result_model.create_from_tmdb_data(movies_data, wizard_id=self.id)

        # Retornar acción para mostrar los resultados en vista tree
        return {
            "type": "ir.actions.act_window",
            "name": f"🎬 Resultados TMDB ({len(movies_data)} de {total_results})",
            "res_model": "tmdb.search.result",
            "view_mode": "list,form",
            "domain": [("id", "in", result_ids)],
            "context": {
                "create": False,
                "edit": False,
                "delete": False,
            },
            "target": "current",  # Abrir en la ventana principal
            "help": """
                <p class="o_view_nocontent_smiling_face">
                    🎬 Resultados de búsqueda TMDB
                </p>
                <p>
                    <strong>Total encontradas:</strong> {total_results} películas<br/>
                    <strong>Mostrando:</strong> {showing} películas
                </p>
                <p>
                    💡 <strong>Acciones disponibles:</strong><br/>
                    • 🔄 <strong>Sincronizar:</strong> Agregar película a tu BD local<br/>
                    • 👁️ <strong>Ver:</strong> Abrir película ya sincronizada<br/>
                    • 🔄 <strong>Actualizar:</strong> Actualizar datos desde TMDB
                </p>
            """.format(total_results=total_results, showing=len(movies_data)),
        }

    def action_clear_filters(self):
        """Limpia todos los filtros"""
        self.write(
            {
                "search_query": False,
                "filter_genre": False,
                "genre": False,
                "filter_score": False,
                "minscore": False,
                "maxscore": False,
                "filter_popularity": False,
                "minpopularity": False,
                "maxpopularity": False,
                "filter_year": False,
                "minyear": False,
                "maxyear": False,
            }
        )

        return {
            "type": "ir.actions.act_window",
            "res_model": self._name,
            "res_id": self.id,
            "view_mode": "form",
            "target": "new",
        }
