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

5. Activer la double authentification (recommandé, indispensable sur le VPS) :

   ```sh
   docker compose -f docker-compose.dev.yml run --rm backend python -m app.totp_setup
   ```

   Scanner le QR code avec une application d'authentification (Aegis, Google Authenticator…), saisir le code affiché pour confirmer, puis copier la ligne `JARVIS_TOTP_SECRET=...` dans `.env` et redémarrer. La page de connexion demande alors un code à 6 chiffres.

## Lancement en local

```sh
docker compose -f docker-compose.dev.yml up --build
```

Ouvrir http://localhost:5173 et se connecter. Le code est monté dans les conteneurs : toute modification recharge le backend ou le frontend automatiquement.

Après un ajout ou une mise à jour de dépendance frontend (`package.json`), ajouter `-V` (`--renew-anon-volumes`) : sinon le conteneur garde son ancien `node_modules` et Vite affiche « Failed to resolve import ».

```sh
docker compose -f docker-compose.dev.yml up --build -V
```

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

Revue de presse des cyberattaques et de l'actualité cyber, deux fois par jour. Le collecteur :

1. lit les flux RSS publics du [CERT-FR](https://cert.cyber.gouv.fr/) (alertes, menaces, bulletins ; les avis de vulnérabilité sont volontairement exclus) et de [Zataz](https://www.zataz.com/) ;
2. enregistre les nouveaux articles (titre, lien, résumé en texte brut). Le XML est analysé de façon sûre : taille limitée, entités refusées, liens `https` uniquement, paramètres de pistage retirés ;
3. ajoute ces articles au résumé du jour (les deux passages de la journée se cumulent) ;
4. si une clé Claude est configurée : rédige une revue d'environ 5 minutes (« À retenir », « Autres actualités », « Pour comprendre »).

Une source en panne n'empêche pas les autres d'être lues ; la collecte n'échoue que si toutes les sources sont injoignables. Au premier lancement, seuls les articles des dernières 48 h comptent comme nouveaux, les plus anciens sont gardés en historique.

Lancer une collecte à la main :

```sh
docker compose -f docker-compose.dev.yml run --rm backend python -m app.collect veille_cyber
```

Configuration (dans `.env`, voir `.env.example`) :

- `ANTHROPIC_API_KEY` : optionnelle. Sans elle, la fenêtre affiche seulement la liste des articles. Seuls des articles de presse publics (titre, résumé, source) sont envoyés à l'API ; chaque appel est journalisé (modèle, tokens, coût estimé) dans la table `llm_calls`, et le coût du mois s'affiche dans la fenêtre.

### Planification (serveur)

Les fichiers `deploy/systemd/jarvis-veille.service` et `.timer` lancent la collecte chaque jour à 6h30 et 18h30 (heure de Paris), en rattrapant une exécution manquée après un redémarrage :

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

## Module OSINT

Surveillance hebdomadaire de **ta propre** exposition publique, et de personne d'autre :

- **Fuites de données** : ton e-mail est vérifié auprès de [XposedOrNot](https://xposedornot.com) (API gratuite).
- **Profil Gravatar** : seul un hash SHA-256 de l'e-mail est envoyé.
- **Pseudos** : existence de comptes via les API publiques de GitHub, GitLab, Codeberg, Keybase, Hacker News et Chess.com.
- **Mentions** : nom et numéro de téléphone recherchés en expression exacte via l'[API Brave Search](https://brave.com/search/api/) (clé `JARVIS_BRAVE_API_KEY`, optionnelle).

Le rapport de la semaine liste uniquement les nouveautés ; l'historique complet reste consultable. Aucun scraping, aucun appel à Claude : les données OSINT ne quittent le serveur que vers les services interrogés ci-dessus.

Configuration : copier `data/osint.example.toml` en `data/osint.toml` (non commité) et y mettre tes identifiants. La base ne stocke que des étiquettes (« e-mail perso », « téléphone mobile ») et les pseudos ; les journaux ne contiennent aucun identifiant.

```sh
docker compose -f docker-compose.dev.yml run --rm backend python -m app.collect osint
```

Sur le serveur : `deploy/systemd/jarvis-osint.service` et `.timer` (chaque lundi à 7h), installés comme ceux de la veille cyber.

## Module Leboncoin

Liste les annonces reçues par les **alertes e-mail de tes recherches sauvegardées** sur Leboncoin, sans doublons, avec l'historique des prix. C'est la seule source : aucun scraping, aucune requête vers leboncoin.fr, aucune image chargée.

Mise en place :

1. Créer une adresse e-mail **dédiée** aux alertes (pas ta boîte principale), activer l'IMAP et générer un mot de passe d'application.
2. Dans Leboncoin, envoyer les alertes des recherches sauvegardées vers cette adresse.
3. Renseigner `JARVIS_LBC_IMAP_*` dans `.env` (voir `.env.example`).

Toutes les heures, le collecteur lit en IMAP (TLS, dossier ouvert **en lecture seule** : rien n'est marqué lu, déplacé ni supprimé) les e-mails des 14 derniers jours qu'il n'a pas encore traités. Un e-mail n'est accepté que si ton fournisseur a vérifié sa signature DKIM pour `leboncoin.fr` et que l'expéditeur est bien Leboncoin : une fausse alerte envoyée à la boîte est ignorée. La base ne garde que les données publiques des annonces (titre, prix, lieu, lien), jamais le contenu des e-mails ; les journaux ne contiennent que des compteurs.

> **En pause (branche `feat/leboncoin`, non fusionnée).** L'extraction des annonces depuis le HTML des alertes (`extract_ads` dans `backend/modules/leboncoin/parser.py`) n'est pas encore écrite : elle attend de vrais e-mails d'exemple. D'ici là, les alertes sont comptées en `parse_errors` et seront relues automatiquement une fois le parseur prêt (si elles ont moins de 14 jours).
>
> Pour reprendre :
> 1. Boîte Gmail dédiée : validation en deux étapes active, puis mot de passe d'application sur myaccount.google.com/apppasswords. Mettre `JARVIS_LBC_IMAP_HOST=imap.gmail.com` et les identifiants dans `.env`.
> 2. Faire arriver les alertes dans cette boîte, de préférence par un filtre de transfert depuis la boîte du compte Leboncoin, pour que la boîte dédiée ne reçoive pas les e-mails de réinitialisation du mot de passe.
> 3. Déposer 2 ou 3 alertes réelles en `.eml` dans `data/` (Gmail : ⋮ → Télécharger le message), puis écrire `extract_ads` et ses tests à partir de ces exemples anonymisés.

```sh
docker compose -f docker-compose.dev.yml run --rm backend python -m app.collect leboncoin
```

Sur le serveur : `deploy/systemd/jarvis-leboncoin.service` et `.timer` (toutes les heures), installés comme ceux de la veille cyber.

### Aide à la vente (onglet « Mes ventes »)

Pour chaque objet à vendre : état, détails, prix demandé et prix plancher, statut (en préparation, en vente, vendu, retiré). **Jarvis ne publie rien et n'envoie aucun message** : il prépare, tu relis, copies et publies toi-même.

- **Brouillon d'annonce** : rédigé par Claude (petit modèle, appel journalisé dans `llm_calls`) si `ANTHROPIC_API_KEY` est définie, sinon par un gabarit simple. Seuls l'objet, l'état, le prix et les détails sont envoyés ; les e-mails, numéros de téléphone et IBAN éventuellement tapés dans les détails sont retirés avant l'envoi. N'y mets quand même pas tes coordonnées.
- **Annonces comparables** : annonces déjà collectées par les alertes dont le titre contient tous les mots-clés de l'objet, avec la médiane et la fourchette de prix. Vide tant que la lecture des alertes n'est pas branchée.
- **Rappel de baisse** : si l'objet est en vente depuis N jours (14 par défaut) sans changement de prix, la fenêtre propose une baisse de 10 %, jamais sous le prix plancher. « J'ai baissé le prix » enregistre la baisse une fois faite sur Leboncoin.

### Analyse d'annonces (onglet « Analyser »)

Tu colles le texte d'une annonce repérée sur Leboncoin (titre, prix, description, lieu) et Jarvis dit si c'est une **bonne affaire, un prix correct ou une mauvaise affaire**. Tes critères restent dans les filtres de tes recherches Leboncoin. Jarvis **ne lit pas leboncoin.fr** : aucun lien n'est ouvert, seul le texte collé est utilisé.

- **Sans Claude** (toujours fait) : prix lu dans le texte, annonces comparables déjà collectées (mots-clés tirés du titre ou saisis), et signaux d'arnaque simples : paiement par virement, mandat ou PayPal « entre amis », coupons prépayés, échange par WhatsApp/SMS, envoi uniquement, vendeur à l'étranger, urgence, coordonnées dans l'annonce, prix sous la moitié de la médiane des comparables. Un signal n'est pas une preuve.
- **Avec Claude** (si `ANTHROPIC_API_KEY` est définie) : verdict, liste de ce que dit l'annonce (point positif, négatif ou neutre), fiabilité du modèle grâce à **5 recherches web au maximum**, avis sur le prix et le risque d'arnaque, questions à poser au vendeur, et liens vers les sources.
- **Fiche voiture** (si l'annonce concerne un véhicule) : état de la carte grise (au nom du vendeur, gage, HistoVec), état du contrôle technique (moins de 6 mois pour un véhicule de plus de 4 ans, contre-visite, défaillances), réparations à prévoir avec leur urgence et une fourchette de prix, et **coût estimé** = prix + carte grise + réparations. Claude estime chaque poste ; l'addition est faite par le backend. Les coûts restent des estimations : fais inspecter la voiture avant d'acheter. Les recherches sont faites par l'API Claude (outil `web_search`, leboncoin.fr exclu) et coûtent 0,01 $ chacune en plus des tokens ; `llm_calls` enregistre le nombre de recherches et le coût estimé. Une analyse prend jusqu'à une minute.
- **Données** : les e-mails, numéros de téléphone et IBAN sont retirés du texte avant l'envoi à Claude et avant l'enregistrement. Le texte de l'annonce est traité comme une donnée non fiable (il peut contenir des consignes piégées) : il est isolé dans le prompt et les résultats sont affichés en texte brut, seuls les liens `https` étant cliquables.

C'est une aide indicative : vérifie toi-même et ne paie jamais en dehors de Leboncoin.

## Sécurité

- `.env` n'est jamais commité ; `.env.example` documente chaque variable.
- Un seul compte, mot de passe haché (argon2), sessions côté serveur (cookie `HttpOnly`, `SameSite=Strict`), connexion bloquée 15 minutes après 5 échecs.
- Double authentification TOTP (RFC 6238) si `JARVIS_TOTP_SECRET` est défini : code à 6 chiffres, tolérance de ±30 s, un code déjà utilisé est refusé. Sans secret, le backend affiche un avertissement au démarrage. Les deux facteurs sont toujours vérifiés et l'erreur ne dit pas lequel est faux.
- Téléphone perdu ou changé : relancer `python -m app.totp_setup`, remplacer `JARVIS_TOTP_SECRET` dans `.env` et redémarrer ; l'ancien secret ne fonctionne plus. Le secret TOTP est aussi sensible que le hash du mot de passe : il ne quitte jamais `.env`.
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
