from odoo import models, fields, api
from odoo.exceptions import UserError


class TMDBMovieSearchWizard(models.TransientModel):
    _name = "tmdb.movie.search.wizard"
    _description = "TMDB Movie Search Wizard"

    search_query = fields.Char(string="Search Query")
    limit = fields.Integer(string="Limit", default=20)
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
            if record.limit and (record.limit < 1 or record.limit > 100):
                raise UserError("Limit must be between 1 and 100")

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
            "res_id": movies.ids[0] if movies else False,
            "view_mode": "list,form",
            "domain": [("id", "in", movies.ids)],
            "name": f"Resultados de búsqueda ({len(movies)} películas)",
            "target": "current",
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
