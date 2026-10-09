# CLAUDE.md – Projet Jarvis

## Contexte
Jarvis est un dashboard web personnel, de type « bureau » avec une fenêtre par module. Chaque module collecte des informations et les affiche dans sa fenêtre. Il est utilisé par une seule personne : le propriétaire du dépôt.

Le propriétaire est étudiant en 2e année de Bachelor Informatique et Sécurité informatique. Il connaît les bases (Python, git, terminal) mais n'est pas expert. Explique brièvement tes choix techniques, privilégie les solutions simples et lisibles, et signale tout ce qui touche à la sécurité.

Langue : réponds et commente en français. Le code, les noms de variables et les messages de commit restent en anglais.

## Stack
- Backend : Python 3.12+, FastAPI, SQLite (SQLAlchemy ou sqlite3 standard, à valider en plan mode).
- Frontend : React + Vite, interface en fenêtres déplaçables. Le style visuel sera défini plus tard : reste sobre.
- Déploiement : Docker Compose sur un petit VPS. Accès uniquement via réseau privé (Tailscale ou équivalent) avec authentification applicative en plus. Aucun port applicatif exposé sur Internet.
- Développement : en local d'abord. Le déploiement cloud vient après les étapes 0 et 1.

## Architecture
- Un module = un dossier `backend/modules/<nom>/` avec : un collecteur (Python classique, sans appel à un LLM), un schéma de données, une route API, et une fenêtre `frontend/src/windows/<Nom>Window.tsx`.
- Les collecteurs écrivent dans SQLite. Le dashboard ne fait que lire via l'API.
- Les tâches récurrentes sont lancées par un planificateur sur le serveur (cron ou systemd timer, à choisir en plan mode).
- Les appels à l'API Claude sont réservés au résumé et à l'analyse, avec un petit modèle, et sont journalisés (modèle, nombre de tokens) pour mesurer le coût.

Structure cible :
```
backend/
  app/            # FastAPI, auth, config
  modules/        # un dossier par module
  tests/
frontend/
  src/windows/    # une fenêtre par module
docker-compose.yml
.env.example
CLAUDE.md
```

## Modules prévus (ordre de réalisation)
0. Squelette : dépôt, structure, authentification, dashboard avec fenêtres vides.
1. Veille cyber : flux CISA KEV (JSON public), API NVD, score EPSS ; résumé quotidien d'environ 5 minutes ; mini-fiche pédagogique pour tout logiciel absent de `data/skills.md` (liste des compétences du propriétaire, qu'il fournira).
2. Suivi financier : saisie manuelle, taux officiels (Livret A, Livret Jeune), plafonds, objectifs d'épargne. Comptes actuels : Livret A, Livret Jeune, compte courant, compte pro.
3. OSINT sur le propriétaire uniquement : mentions du nom, exposition de l'e-mail, pseudos, numéro de téléphone (liste d'identifiants à fournir). Rapport hebdomadaire.
4. Annonces Leboncoin : analyse des annonces reçues par alertes e-mail, puis aide à la vente (annonce, prix, rappels). Précisions à venir pendant le développement.

Projet mis de côté : comparateur d'assurances.

## Règles impératives
**Sécurité et données**
- Aucun secret dans le code ni dans git : tout passe par `.env` (jamais commité) et `.env.example` documenté.
- Le dashboard contient des données financières et des résultats d'OSINT : authentification obligatoire, requêtes paramétrées uniquement, dépendances à jour, journaux sans données personnelles.
- Les données personnelles restent sur le serveur. N'envoie à l'API Claude que le strict minimum, jamais d'identifiants, de numéros de compte ni de mots de passe.
- Ne stocke jamais de mots de passe ni de numéros de carte ou de compte bancaire.

**Limites légales et conditions d'utilisation**
- Ne contourne pas la protection anti-bot de Leboncoin ou d'un autre site : pas de scraping, pas de proxys résidentiels, pas de résolution de captcha.
- Pour Leboncoin, la source de données est uniquement les alertes e-mail de recherches sauvegardées par le propriétaire.
- Ne publie rien et n'envoie aucun message à la place du propriétaire : tu prépares les brouillons, il envoie et publie lui-même.
- Le suivi financier fournit de l'information, pas du conseil en investissement personnalisé : mentionne que ce n'est pas du conseil financier. Les règles fiscales et les taux se vérifient à la source au moment de l'usage.
- L'OSINT ne concerne que le propriétaire lui-même.

## Méthode de travail
- Commence chaque tâche en mode plan et attends la validation avant d'écrire du code.
- Avance par petites étapes testables : un module, une route, une fenêtre à la fois.
- Écris des tests pour les collecteurs (avec des données de test enregistrées, sans réseau) et pour les routes.
- Après chaque étape : lance les tests et le linter, puis résume en deux ou trois phrases ce qui change.
- Commits petits et clairs, une branche par module.
- Si une API, une version de bibliothèque ou une règle externe est incertaine, vérifie la documentation officielle avant de coder.
- En cas de doute sur un choix d'architecture, pose la question plutôt que de décider seul.

## Commandes
Tout passe par Docker (aucun outil local requis hormis Docker). Depuis la racine du dépôt :
- Lancer en dev (backend + frontend, rechargement auto) : `docker compose -f docker-compose.dev.yml up --build` → http://localhost:5173
- Générer le hash du mot de passe : `docker compose -f docker-compose.dev.yml run --rm backend python -m app.hash_password`
- Tests backend : `docker compose -f docker-compose.dev.yml run --rm backend pytest`
- Lint backend : `docker compose -f docker-compose.dev.yml run --rm backend sh -c "ruff check && ruff format --check"`
- Lint + build frontend : `docker compose -f docker-compose.dev.yml run --rm frontend sh -c "npm run lint && npm run build"` (linter : oxlint, fourni par le gabarit Vite)
- Lancer un collecteur : `docker compose -f docker-compose.dev.yml run --rm backend python -m app.collect <module>` (ex. `veille_cyber`)
- Nouvelle migration après modification des modèles : `docker compose -f docker-compose.dev.yml run --rm backend alembic revision --autogenerate -m "..."` (relire le fichier généré)
- Stack de déploiement : `docker compose up -d --build` → http://127.0.0.1:8080 (port modifiable via `JARVIS_HTTP_PORT`)

## Définition de « terminé » pour l'étape 0
- Le dépôt s'installe et se lance en local avec une seule commande documentée.
- Le dashboard affiche une fenêtre par module (vides), après connexion.
- Les secrets sont dans `.env`, avec un `.env.example` à jour.
- Un test minimal passe et un `README` explique l'installation.
- Un `docker-compose.yml` fonctionnel existe pour le déploiement futur.
