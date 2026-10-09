# Jarvis

Dashboard web personnel en fenêtres : chaque module (veille cyber, finances, OSINT, Leboncoin) collecte des informations et les affiche dans sa fenêtre.

- Backend : Python 3.12+, FastAPI, SQLite (SQLAlchemy)
- Frontend : React + Vite + TypeScript, fenêtres déplaçables (react-rnd)
- Exécution : Docker Compose

## Prérequis

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (ou Docker Engine + Compose v2), démarré.
- Optionnel, pour l'éditeur : [uv](https://docs.astral.sh/uv/) et Node.js 24.

## Installation

1. Créer le fichier de configuration à partir de l'exemple :

   ```sh
   cp .env.example .env
   ```

2. Générer une clé secrète et la coller dans `JARVIS_SECRET_KEY` :

   ```sh
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. Choisir un mot de passe (12 caractères minimum) et générer son hash :

   ```sh
   docker compose -f docker-compose.dev.yml run --rm backend python -m app.hash_password
   ```

   Copier la ligne `JARVIS_PASSWORD_HASH='...'` affichée dans `.env`, **avec les apostrophes** (le hash contient des `$`). Le mot de passe lui-même n'est stocké nulle part.

4. Ajuster `JARVIS_ADMIN_USERNAME` si besoin.

## Lancement en local

```sh
docker compose -f docker-compose.dev.yml up --build
```

Ouvrir http://localhost:5173 et se connecter. Le code est monté dans les conteneurs : toute modification recharge le backend ou le frontend automatiquement.

## Tests et lint

```sh
docker compose -f docker-compose.dev.yml run --rm backend pytest
docker compose -f docker-compose.dev.yml run --rm backend sh -c "ruff check && ruff format --check"
docker compose -f docker-compose.dev.yml run --rm frontend sh -c "npm run lint && npm run build"
```

## Déploiement (aperçu)

```sh
docker compose up -d --build
```

nginx sert le frontend et relaie `/api` vers le backend, sur `127.0.0.1:8080` uniquement (port modifiable avec `JARVIS_HTTP_PORT`). Sur le VPS, l'accès se fera par Tailscale : aucun port applicatif n'est exposé sur Internet. Mettre `JARVIS_COOKIE_SECURE=true` dès que le dashboard est servi en HTTPS.

## Module Veille cyber

Chaque matin, le collecteur :

1. télécharge le catalogue [CISA KEV](https://www.cisa.gov/known-exploited-vulnerabilities-catalog) (vulnérabilités activement exploitées) ;
2. récupère dans la [NVD](https://nvd.nist.gov/developers/vulnerabilities) le détail des nouvelles entrées KEV et les CVE critiques publiées depuis la dernière collecte ;
3. ajoute le score [EPSS](https://www.first.org/epss/) (probabilité d'exploitation à 30 jours) ;
4. si une clé Claude est configurée : rédige un résumé d'environ 5 minutes et une fiche pédagogique pour chaque logiciel absent de `data/skills.md` (5 fiches maximum par jour).

Lancer une collecte à la main :

```sh
docker compose -f docker-compose.dev.yml run --rm backend python -m app.collect veille_cyber
```

Configuration (dans `.env`, voir `.env.example`) :

- `ANTHROPIC_API_KEY` : optionnelle. Sans elle, la fenêtre affiche la liste brute triée par priorité. Seules des données publiques (CVE, produits, scores) sont envoyées à l'API ; chaque appel est journalisé (modèle, tokens, coût estimé) dans la table `llm_calls`, et le coût du mois s'affiche dans la fenêtre.
- `JARVIS_NVD_API_KEY` : optionnelle et gratuite ; sans elle, le collecteur attend 6 s entre deux requêtes NVD.
- `data/skills.md` : copier `data/skills.example.md` et lister les logiciels connus. Ce fichier n'est pas commité et n'est jamais envoyé à Claude.

### Planification (serveur)

Les fichiers `deploy/systemd/jarvis-veille.service` et `.timer` lancent la collecte chaque jour à 6h30 (heure de Paris), en rattrapant une exécution manquée après un redémarrage :

```sh
sudo cp deploy/systemd/jarvis-veille.* /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now jarvis-veille.timer
systemctl list-timers jarvis-veille.timer      # prochaine exécution
journalctl -u jarvis-veille.service            # journaux
```

Adapter `WorkingDirectory` si le dépôt n'est pas dans `/opt/jarvis`.

## Module Finances

Suivi manuel des comptes (Livret A, Livret Jeune, compte courant, compte pro) : **information indicative, pas un conseil en investissement**.

- **Relevés de solde** : noter de temps en temps le solde de chaque compte à une date (un relevé par compte et par jour ; le ressaisir le remplace). Montants en euros, stockés en centimes.
- **Taux** : saisis à la main après vérification à la source ([Livret A sur service-public.fr](https://www.service-public.fr/particuliers/vosdroits/F2365), [Livret Jeune sur economie.gouv.fr](https://www.economie.gouv.fr/particuliers/gerer-mon-argent/gerer-mon-budget-et-mon-epargne/livret-jeune-quelles-sont-ses-caracteristiques)). La fenêtre signale « à vérifier » après chaque révision officielle (1er février, 1er août) et si le Livret Jeune passe sous le Livret A.
- **Plafonds** : pré-remplis (22 950 € et 1 600 €, versements hors intérêts capitalisés), modifiables ; alerte au-delà de 90 %.
- **Intérêts** : estimation sur 12 mois (solde × taux). Le calcul réel se fait par quinzaines.
- **Objectifs** : sur un compte ou sur l'ensemble des livrets, avec l'effort mensuel nécessaire si une échéance est fixée.

Aucun numéro de compte, IBAN ou identifiant bancaire n'est stocké : chaque compte n'a qu'un libellé. Les journaux du serveur ne contiennent aucun montant.

## Sécurité

- `.env` n'est jamais commité ; `.env.example` documente chaque variable.
- Un seul compte, mot de passe haché (argon2), sessions côté serveur (cookie `HttpOnly`, `SameSite=Strict`), connexion bloquée 15 minutes après 5 échecs.
- La base SQLite vit dans un volume Docker (`/data`), hors du dépôt.

## Structure

```
backend/
  app/        # FastAPI : config, base, authentification, registre des modules
  modules/    # un dossier par module
  tests/
frontend/
  src/windows/  # une fenêtre par module
docker-compose.yml       # déploiement
docker-compose.dev.yml   # développement
```

Ajouter un module : créer `backend/modules/<id>/__init__.py` (exposant `MODULE` et `router`), puis `frontend/src/windows/<Nom>Window.tsx` et l'enregistrer dans `frontend/src/windows/index.ts`.
