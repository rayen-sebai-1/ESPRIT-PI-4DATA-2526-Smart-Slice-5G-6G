# NeuroSlice Tunisia

Plateforme de supervision intelligente 5G/6G pour la Tunisie, construite en microservices Docker, avec un frontend React professionnel et un backend FastAPI branche sur PostgreSQL.

Le projet est aujourd'hui dans un etat **MVP executable**, avec :

- un frontend web disponible sur `http://localhost:3000`
- 4 microservices backend actifs
- une base PostgreSQL unique
- une authentification JWT par roles
- des datasets reels integres au projet
- 4 moteurs IA deja industrialises en V1
- une couche de fallback pour eviter toute rupture de service

Ce document decrit l'etat **actuel reel** de l'application, ses fonctionnalites, ses utilisateurs, ses KPI, ses APIs, ses interfaces et sa structure.

## 1. Resume executif

**Nom du produit**

- NeuroSlice Tunisia

**Positionnement**

- cockpit de supervision reseau 5G/6G
- orientation NOC / exploitation telecom
- PoC realiste, demontrable, extensible

**Etat de maturite**

- architecture backend reelle et dockerisee
- frontend V1 professionnel deja livre
- donnees de demonstration coherentes
- integration reelle de plusieurs pipelines ML
- encore partiellement base sur seed et snapshots, pas sur donnees live operateur

**Ce qui est deja disponible**

- authentification et controle d'acces par role
- dashboard national
- dashboard regional
- monitoring des sessions
- centre de predictions
- catalogue des modeles
- cartes KPI, tableaux, badges de statut, graphiques et carte stylisee de la Tunisie

**Ce qui n'est pas encore livre**

- Admin Panel frontend
- vue Congestion dediee
- vue Anomaly dediee
- vue Manager Summary dediee
- api-gateway
- alert-service
- region-service separe

## 2. Vision fonctionnelle

L'application vise a superviser un reseau 5G/6G regionalise sur la Tunisie, en combinant :

- des KPI nationaux et regionaux
- des sessions reseau detaillees
- des scores IA de SLA, congestion et anomalies
- des recommandations d'action pour l'operateur
- une architecture prete a brancher des notebooks de machine learning existants

Les regions integrees dans la V1 sont :

- Grand Tunis
- Cap Bon
- Sahel
- Sfax
- Nord Ouest
- Centre Ouest
- Sud Est
- Sud Ouest

## 3. Architecture actuelle

### 3.1 Vue d'ensemble

Le projet est organise en monorepo avec :

- un frontend React/TypeScript
- 4 microservices FastAPI
- un package Python partage
- une base PostgreSQL commune
- Alembic pour les migrations
- Docker Compose pour l'orchestration locale

### 3.2 Services Docker

| Service | Port local | Role |
|---|---:|---|
| `frontend` | `3000` | interface web utilisateur |
| `auth-service` | `8001` | login, JWT, utilisateur courant, liste utilisateurs |
| `session-service` | `8002` | liste et detail des sessions |
| `prediction-service` | `8003` | predictions, execution, catalogue des modeles |
| `dashboard-service` | `8004` | agregations dashboard national et regional |
| `postgres` | `5432` | base de donnees |
| `db-migrate` | n/a | migrations Alembic + seed |

### 3.3 URLs utiles

- Frontend : `http://localhost:3000`
- Swagger Auth : `http://localhost:8001/docs`
- Swagger Sessions : `http://localhost:8002/docs`
- Swagger Predictions : `http://localhost:8003/docs`
- Swagger Dashboard : `http://localhost:8004/docs`

## 4. Roles utilisateurs

Le systeme gere 3 roles.

### 4.1 ADMIN

Fonctionnellement, l'admin peut :

- se connecter
- voir le dashboard national
- voir le dashboard regional
- voir les sessions
- voir les predictions
- voir la liste des utilisateurs via l'API

Dans la V1 frontend actuelle, l'admin a acces aux routes :

- `/dashboard/national`
- `/dashboard/region`
- `/sessions`
- `/predictions`

### 4.2 NETWORK_OPERATOR

Fonctionnellement, l'operateur peut :

- se connecter
- surveiller le dashboard national
- surveiller le dashboard regional
- consulter les sessions
- consulter les predictions
- relancer une prediction sur une session

Routes frontend accessibles :

- `/dashboard/national`
- `/dashboard/region`
- `/sessions`
- `/predictions`

### 4.3 NETWORK_MANAGER

Fonctionnellement, le manager peut aujourd'hui :

- se connecter
- consulter le dashboard national
- consulter le dashboard regional

Dans la V1 actuelle, il n'a pas acces aux routes :

- `/sessions`
- `/predictions`

Note :

- la vue `Manager Summary` est exposee cote backend via `/dashboard/manager/summary`
- elle n'a pas encore de page frontend dediee

### 4.4 Comptes de demonstration

- `admin@neuroslice.tn / admin123`
- `operator@neuroslice.tn / operator123`
- `manager@neuroslice.tn / manager123`

## 5. Fonctionnalites disponibles

### 5.1 Authentification

- login par email / mot de passe
- creation de JWT
- chargement du profil courant
- navigation conditionnee par role

### 5.2 Supervision nationale

- KPI nationaux
- carte de supervision Tunisie
- regions a risque
- synthese exploitation
- graphique de pression reseau par region

### 5.3 Supervision regionale

- selection de region
- KPI regionaux
- tendance SLA / congestion sur 7 snapshots
- distribution des slices
- recommandations IA
- snapshot exploitation

### 5.4 Monitoring des sessions

- table paginee
- filtres region, slice et niveau de risque
- recherche locale
- vue detail session
- affichage de la prediction la plus recente

### 5.5 Centre de predictions

- vue tabulaire des predictions
- tri fonctionnel par onglet SLA / Congestion / Anomalies
- relance d'une prediction a la demande
- filtre par region et risque
- catalogue des modeles disponibles

## 6. KPI et definitions

Le tableau ci-dessous decrit les KPI visibles dans la V1.

| KPI | Signification | Calcul / origine | Ecran |
|---|---|---|---|
| `SLA National` | niveau global de conformite reseau | moyenne des `sla_score` recents, convertie en pourcentage | Dashboard National |
| `Latence moyenne` | latence moyenne des sessions | moyenne de `sessions.latency_ms` | Dashboard National, Dashboard Regional, Sessions |
| `Congestion rate` | saturation globale estimee | moyenne des `congestion_score` recents, convertie en pourcentage | Dashboard National, Dashboard Regional |
| `Alertes actives` | volume de situations a prioriser | derive du nombre de sessions `HIGH` ou `CRITICAL` | Dashboard National |
| `Sessions` | nombre de sessions suivies | compte de `network.sessions` | Dashboard National |
| `Anomalies` | sessions avec signal anormal significatif | derive des `anomaly_score >= 0.65` | Dashboard National, Dashboard Regional |
| `SLA regional` | conformite d'une region | moyenne SLA sur les sessions de la region | Dashboard Regional |
| `Packet loss` | perte de paquets moyenne | moyenne `packet_loss` par region | Dashboard Regional |
| `Charge reseau` | charge observee sur la region | `regions.network_load` | Dashboard Regional |
| `gNodeB` | sites radio suivis | `regions.gnodeb_count` | Dashboard Regional |
| `Sessions high risk` | sessions critiques ou elevees | nombre de predictions `HIGH` + `CRITICAL` | Dashboard Regional, Predictions |
| `Sessions affichees` | volume de lignes apres filtres | resultat de la page courante | Sessions Monitor |
| `Regions couvertes` | nombre de regions presentes dans la vue | distinct sur la page courante | Sessions Monitor |
| `SLA moyen` | moyenne des scores SLA visibles | moyenne page predictions | Predictions Center |
| `Congestion moyenne` | moyenne des scores congestion visibles | moyenne page predictions | Predictions Center |
| `Anomalie moyenne` | moyenne des scores anomalies visibles | moyenne page predictions | Predictions Center |

Important :

- il n'y a pas encore de `alert-service`
- la notion d'"alerte active" est donc **derivee** du niveau de risque et non d'une table d'alertes autonome

## 7. Labels, badges et conventions visuelles

### 7.1 Labels de risque

| Label | Sens | Couleur UI |
|---|---|---|
| `LOW` | faible exposition | vert |
| `MEDIUM` | vigilance | orange |
| `HIGH` | risque important | rouge |
| `CRITICAL` | situation critique | rouge fonce |

### 7.2 Labels de statut RIC

| Label | Sens | Couleur UI |
|---|---|---|
| `HEALTHY` | region stable | vert |
| `DEGRADED` | degradation observee | orange |
| `CRITICAL` | zone critique | rouge |
| `MAINTENANCE` | maintenance / indisponibilite pilotee | gris |

### 7.3 Labels de statut modele

| Label | Sens |
|---|---|
| `ACTIVE` | modele charge et utilise |
| `FALLBACK` | modele de secours encore exploite |
| `PLANNED` | integration prevue mais non encore branchee |
| `MISSING_ARTIFACTS` | provider pret mais artefacts absents |
| `ERROR` | artefacts trouves mais chargement en erreur |

## 8. Interfaces frontend V1

La navigation actuelle est composee de :

- une sidebar fixe a gauche
- une topbar sticky
- des cartes KPI
- des tableaux operateur
- des graphiques Recharts
- des badges de statut

### 8.1 Sidebar

**Nom produit affiche**

- `NeuroSlice Tunisia`
- sous-titre : `NOC supervision`

**Bloc information**

- label : `Plateforme`
- texte : cockpit reseau 5G/6G branche au backend MVP existant

**Entrees de navigation**

- `Dashboard National`
- `Dashboard Regional`
- `Sessions Monitor`
- `Predictions Center`

**Bloc bas de sidebar**

- label : `Mode V1`
- bouton : `Stack active`

### 8.2 Topbar

**Labels visibles**

- `Network supervision`
- `Derniere synchro`
- `Services FastAPI actifs`
- nom complet de l'utilisateur
- role utilisateur
- `Deconnexion`

### 8.3 Interface Login

**Route**

- `/login`

**Labels principaux**

- `Telecom AI supervision platform`
- `NeuroSlice Tunisia`
- `Auth par role`
- `Predictions IA`
- `Execution locale`
- `Access control`
- `Connexion plateforme`
- `Email`
- `Mot de passe`
- `Se connecter`

**Comptes de demo proposes dans l'UI**

- `Admin`
- `Operator`
- `Manager`

**Message d'erreur**

- `Identifiants invalides. Verifiez email et mot de passe.`

### 8.4 Interface Dashboard National

**Route**

- `/dashboard/national`

**Labels principaux**

- `National command center`
- `Dashboard National`
- bouton de refresh : `Derniere generation <date>`

**Cartes KPI**

- `SLA National`
- `Latence moyenne`
- `Congestion rate`
- `Alertes actives`
- `Sessions`
- `Anomalies`

**Blocs et sections**

- `Pression reseau par region`
- `Carte de supervision Tunisie`
- `Top regions a risque`
- `Synthese exploitation`

**Blocs de fallback actuellement visibles**

- `Evolution SLA nationale en attente`
- `Distribution nationale des slices en attente`

Ces deux blocs indiquent proprement qu'un endpoint plus riche n'est pas encore expose.

### 8.5 Interface Dashboard Regional

**Routes**

- `/dashboard/region`
- `/dashboard/region/:regionId`

**Labels principaux**

- `Regional supervision`
- `Dashboard Regional`

**Actions en haut de page**

- badge `RIC status`
- select de region

**Cartes KPI**

- `SLA regional`
- `Latency moyenne`
- `Packet loss`
- `Charge reseau`
- `gNodeB`
- `Sessions high risk`

**Blocs et sections**

- `Tendance regionale`
- `Distribution des slices`
- `Activite IA et recommandations`
- `Snapshot exploitation`
- bouton operateur : `Ouvrir les sessions de la region`

### 8.6 Interface Sessions Monitor

**Route**

- `/sessions`

**Labels principaux**

- `Operational sessions`
- `Sessions Monitor`

**Filtres**

- recherche : `Rechercher une session ou une region...`
- `Toutes les regions`
- `Tous les risques`
- `Tous les slices`

**Cartes KPI**

- `Sessions affichees`
- `High risk`
- `Latency moyenne`
- `Regions couvertes`

**Table**

Colonnes visibles :

- `Session`
- `Region`
- `Slice`
- `Qualite radio`
- `Prediction`
- `Action IA`
- `Detail`

**Actions**

- bouton `Ouvrir`
- pagination `Precedent`
- pagination `Suivant`

**Etat vide**

- `Aucune session`

### 8.7 Interface Session Detail Drawer

Le detail session s'ouvre en panneau lateral depuis `Sessions Monitor`.

**Labels visibles**

- `Session detail`
- `Inspection temps reel`
- `KPI radio`
- `Contexte reseau`
- `Lecture IA`
- `Action recommandee`

**KPIs detail session**

- `Latency`
- `Packet loss`
- `Throughput`
- `Slice source`
- `Region`
- `Code`
- `Load reseau`
- `gNodeB`
- `SLA`
- `Congestion`
- `Anomalie`

### 8.8 Interface Predictions Center

**Route**

- `/predictions`

**Labels principaux**

- `AI monitoring`
- `Predictions Center`

**Actions haut de page**

- select `Toutes les regions`
- select `Tous les risques`
- bouton `Rafraichir`

**Onglets**

- `SLA`
- `Congestion`
- `Anomalies`
- `Models`

**Cartes KPI**

- `SLA moyen`
- `Congestion moyenne`
- `Anomalie moyenne`
- `Sessions high risk`

**Table**

Colonnes visibles :

- `Session`
- `Region`
- `SLA`
- `Congestion`
- `Anomalie`
- `Risque`
- `Modele`
- `Action IA`
- `Run`

**Actions**

- bouton `Relancer`
- pagination `Precedent`
- pagination `Suivant`

**Bloc lateral**

- `Focus prioritaire`

**Messages runtime**

- `Prediction relancee avec succes.`
- `La relance a echoue. Verifie prediction-service.`

### 8.9 Interface Models Catalog

L'onglet `Models` du `Predictions Center` affiche le catalogue technique des moteurs IA.

**Labels de carte**

- `Implementation`
- `Status`
- `Notebook source`
- `Artifact`

**Fallbacks prevus**

- `Chargement du catalogue des modeles...`
- `Catalogue indisponible`
- `Aucun modele expose`

## 9. Etat reel des modeles IA

Le projet n'est plus uniquement un mock. L'etat actuel est le suivant.

| Moteur | Statut actuel | Source | Nature de l'integration |
|---|---|---|---|
| `sla-boosting-adapter` | `ACTIVE` | `SLA_5G_Modeling.ipynb` | modele reel exporte en artefacts V1 |
| `congestion-timeseries-adapter` | `ACTIVE` | `network_slicing_congestion_LSTM.ipynb` | adapter reel sur dataset temporel, plus leger que le notebook LSTM |
| `anomaly-misrouting-adapter` | `ACTIVE` | `slice_misrouting_anomaly_pipeline.ipynb` | adapter reel `IsolationForest + runtime rules` |
| `mock-telecom-heuristic` | `FALLBACK` | n/a | securite fonctionnelle et slice fallback |
| `slice-lightgbm-adapter` | `ACTIVE` | `LightGBM_Only.ipynb` | classifieur slice multiclasse derive du notebook |

### 9.1 Verite fonctionnelle sur les modeles

Le produit est aujourd'hui :

- **reel techniquement**
- **reel applicativement**
- **semi-reel metier**

Cela signifie :

- les services, l'UI, la base, Docker et les APIs sont reels
- les datasets sources sont reels et copies dans le projet
- plusieurs modeles sont reels et charges
- les donnees visibles a l'ecran restent des donnees de demonstration seedees, pas des donnees live d'un vrai operateur

### 9.2 Precision importante sur la V1

- le moteur SLA utilise un vrai artefact exporte, mais sur une cible `sla_met` reconstruite a partir du dataset disponible
- le moteur congestion n'est pas un export exact du notebook PyTorch LSTM; c'est un adapter V1 aligne sur les memes features metier
- le moteur anomalies n'est pas un export brut du notebook; il reprend la logique du pipeline avec un chargement industrialise et des regles runtime de misrouting

## 10. Datasets et actifs de reference

Les sources officielles actuellement copiees dans le projet sont referencees dans `data/reference_assets_manifest.json`.

### 10.1 Datasets

| Fichier | Usage principal | Lignes | Colonnes |
|---|---|---:|---:|
| `data/raw/train_dataset.csv` | SLA + slice classification | 31583 | 17 |
| `data/raw/network_slicing_dataset_v3.csv` | anomalies / misrouting | 10000 | 13 |
| `data/raw/network_slicing_dataset_enriched_timeseries.csv` | congestion temporelle | 21600 | 21 |

### 10.2 PDF projet

- `data/reference/Project_1_Network_Slicing.pdf`

Etat actuel :

- le PDF est stocke dans le projet comme reference
- il n'a pas encore ete parse automatiquement ni transforme en documentation structuree

## 11. Catalogue des APIs

Toutes les APIs utilisent JWT bearer.

### 11.1 Auth Service

**Base URL**

- `http://localhost:8001`

**Endpoints**

| Methode | Route | Role requis | Description |
|---|---|---|---|
| `GET` | `/health` | aucun | statut du service |
| `POST` | `/auth/login` | aucun | login et emission du JWT |
| `GET` | `/auth/me` | utilisateur connecte | profil courant |
| `GET` | `/users` | `ADMIN` | liste des utilisateurs |

**Payload login**

```json
{
  "email": "admin@neuroslice.tn",
  "password": "admin123"
}
```

**Reponse login**

```json
{
  "access_token": "eyJhbGciOi...",
  "token_type": "bearer",
  "expires_in": 10800,
  "user": {
    "id": 1,
    "full_name": "Administrateur NeuroSlice",
    "email": "admin@neuroslice.tn",
    "role": "ADMIN",
    "is_active": true
  }
}
```

### 11.2 Session Service

**Base URL**

- `http://localhost:8002`

**Endpoints**

| Methode | Route | Role requis | Description |
|---|---|---|---|
| `GET` | `/health` | aucun | statut du service |
| `GET` | `/sessions` | `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER` | liste paginee des sessions |
| `GET` | `/sessions/{session_id}` | `ADMIN`, `NETWORK_OPERATOR`, `NETWORK_MANAGER` | detail d'une session |

**Filtres supportes**

- `region`
- `risk`
- `slice`
- `page`
- `page_size`

**Structure de `SessionSummary`**

- `id`
- `session_code`
- `region`
  - `id`
  - `code`
  - `name`
  - `ric_status`
  - `network_load`
  - `gnodeb_count`
- `slice_type`
- `latency_ms`
- `packet_loss`
- `throughput_mbps`
- `timestamp`
- `prediction`
  - `id`
  - `sla_score`
  - `congestion_score`
  - `anomaly_score`
  - `risk_level`
  - `predicted_slice_type`
  - `slice_confidence`
  - `recommended_action`
  - `model_source`
  - `predicted_at`

### 11.3 Prediction Service

**Base URL**

- `http://localhost:8003`

**Endpoints**

| Methode | Route | Role requis | Description |
|---|---|---|---|
| `GET` | `/health` | aucun | statut du service |
| `GET` | `/models` | tous roles connectes | catalogue des modeles |
| `GET` | `/predictions` | tous roles connectes | liste paginee des predictions |
| `GET` | `/predictions/{session_id}` | tous roles connectes | prediction la plus recente d'une session |
| `POST` | `/predictions/run/{session_id}` | `ADMIN`, `NETWORK_OPERATOR` | relance prediction unitaire |
| `POST` | `/predictions/run-batch` | `ADMIN`, `NETWORK_OPERATOR` | relance prediction batch |

**Filtres supportes sur `/predictions`**

- `region`
- `risk`
- `page`
- `page_size`

**Payload batch**

```json
{
  "region_id": 1,
  "limit": 20
}
```

**Structure de `PredictionResponse`**

- `id`
- `session_id`
- `session_code`
- `region`
  - `id`
  - `code`
  - `name`
  - `ric_status`
  - `network_load`
- `sla_score`
- `congestion_score`
- `anomaly_score`
- `risk_level`
- `predicted_slice_type`
- `slice_confidence`
- `recommended_action`
- `model_source`
- `predicted_at`

### 11.4 Dashboard Service

**Base URL**

- `http://localhost:8004`

**Endpoints**

| Methode | Route | Role requis | Description |
|---|---|---|---|
| `GET` | `/health` | aucun | statut du service |
| `GET` | `/dashboard/national` | tous roles connectes | overview national + comparaison regions |
| `GET` | `/dashboard/region/{region_id}` | tous roles connectes | vue regionale detaillee |
| `GET` | `/dashboard/manager/summary` | tous roles connectes | synthese management exposee cote backend |

**Structure `NationalOverview`**

- `sla_national_percent`
- `avg_latency_ms`
- `congestion_rate`
- `active_alerts_count`
- `sessions_count`
- `anomalies_count`
- `generated_at`

**Structure `RegionComparison`**

- `region_id`
- `code`
- `name`
- `ric_status`
- `network_load`
- `gnodeb_count`
- `sessions_count`
- `sla_percent`
- `avg_latency_ms`
- `avg_packet_loss`
- `congestion_rate`
- `high_risk_sessions_count`
- `anomalies_count`

## 12. Base de donnees

### 12.1 Schemas PostgreSQL

- `auth`
- `network`
- `monitoring`
- `dashboard`

### 12.2 Tables principales

**`auth.users`**

- utilisateurs applicatifs
- email unique
- role
- mot de passe hash

**`network.regions`**

- metadonnees regionales
- code region
- nom
- statut RIC
- niveau de charge
- nombre de gNodeB

**`network.sessions`**

- session reseau
- region associee
- slice source
- KPI radio
- contexte SLA
- contexte congestion
- contexte anomalies / misrouting

**`monitoring.predictions`**

- scores SLA / congestion / anomalies
- niveau de risque
- slice predite
- action recommandee
- source modele
- date de prediction

**`dashboard.dashboard_snapshots`**

- snapshots nationaux et regionaux
- SLA
- latence moyenne
- congestion
- alertes actives derivees
- anomalies
- total sessions

### 12.3 Contraintes metier

- scores `sla_score`, `congestion_score`, `anomaly_score` entre `0` et `1`
- `slice_confidence` entre `0` et `1`
- `network_load` entre `0` et `100`
- compteurs positifs
- integrite referentielle par cles etrangeres

## 13. Seed de demonstration

Le seed est lance par `db-migrate` et cree actuellement :

- 3 utilisateurs
- 8 regions
- 112 sessions
- 112 predictions
- 63 snapshots dashboard

### 13.1 Logique de seed

- Grand Tunis est plus charge et plus sensible
- Sfax et Sahel sont intermediaires
- Sud Ouest est plus leger
- les sessions sont enrichies avec :
  - contexte SLA
  - contexte congestion
  - contexte anomaly / misrouting

### 13.2 Source des donnees seed

Le seed ne recopie pas les datasets bruts dans la base ligne a ligne. Il s'en sert pour :

- construire des profils realistes de sessions
- injecter des features coherentes pour les providers reels
- garder une application de demonstration lisible et performante

## 14. Structure du projet

```text
neuroslice-tunisia/
├── alembic/
├── data/
│   ├── models/
│   ├── raw/
│   ├── reference/
│   └── reference_assets_manifest.json
├── docs/
├── frontend/
├── infra/
│   └── docker/
├── packages/
│   └── neuroslice_common/
├── scripts/
├── services/
│   ├── auth_service/
│   ├── session_service/
│   ├── prediction_service/
│   └── dashboard_service/
├── sql/
├── .env
├── .env.example
├── alembic.ini
├── docker-compose.yml
└── README.md
```

### 14.1 Dossiers importants

**`frontend/`**

- application React
- routing, auth UI, dashboards, sessions, predictions

**`services/`**

- chaque microservice FastAPI avec ses schemas

**`packages/neuroslice_common/`**

- configuration partagee
- DB
- enums
- modeles SQLAlchemy
- securite
- providers ML

**`scripts/`**

- import des datasets
- export des artefacts
- seed

**`data/models/`**

- artefacts de modeles charges par `prediction-service`

## 15. Demarrage local avec Docker

Depuis la racine du projet :

```bash
docker compose up --build -d
```

Pour relancer proprement :

```bash
docker compose down
docker compose up --build -d
```

Pour voir l'etat :

```bash
docker compose ps
docker compose logs -f
```

## 16. Variables d'environnement principales

Fichier :

- `.env`
- `.env.example`

Variables importantes :

- `DATABASE_URL`
- `SECRET_KEY`
- `ACCESS_TOKEN_EXPIRE_MINUTES`
- `PREDICTION_PROVIDER`
- `SLA_MODEL_PATH`
- `SLA_SCALER_PATH`
- `SLA_METADATA_PATH`
- `CONGESTION_MODEL_PATH`
- `CONGESTION_METADATA_PATH`
- `ANOMALY_MODEL_PATH`
- `ANOMALY_METADATA_PATH`
- `REFERENCE_MANIFEST_PATH`

## 17. Limites connues

### 17.1 Fonctionnelles

- pas encore d'Admin Panel frontend
- pas encore de page Congestion dediee
- pas encore de page Anomaly dediee
- pas encore de page Manager Summary dediee
- pas encore de service d'alertes autonome

### 17.2 API

- pas encore d'endpoint temporel national pour la courbe SLA globale
- pas encore d'endpoint dedie pour la distribution nationale des slices
- pas encore d'endpoint `settings`
- pas encore d'endpoint `service status summary` transverse

### 17.3 UX / wording a corriger

Quelques textes de l'UI restent encore issus d'une ancienne phase plus orientee mock, par exemple :

- le sous-texte de certaines cartes `Predictions`
- certaines mentions `provider mock actuel`

L'application fonctionne, mais une passe de wording UX reste a faire pour coller exactement a l'etat reel des modeles actifs.

## 18. Roadmap recommandee

### 18.1 Court terme

- corriger les textes UI devenus obsoletes
- ajouter `Manager Summary` frontend
- ajouter `Congestion View`
- ajouter `Anomaly View`
- ajouter `Admin Panel`

### 18.2 Moyen terme

- comparer et eventuellement ameliorer le classifieur via `Smart_Slice_6G_v3.ipynb`
- exposer de vraies series temporelles nationales
- ajouter un `alert-service`
- ajouter un `region-service`

### 18.3 Long terme

- connecter des donnees live ou quasi-live operateur
- brancher les exports exacts de notebooks en production
- introduire audit, alerting, orchestration et observabilite avancee

## 19. Conclusion

NeuroSlice Tunisia est aujourd'hui une base serieuse de produit de supervision telecom :

- executable en local via Docker
- visuellement credible
- structuree en microservices
- deja branchee a des datasets reels
- deja equipee de plusieurs moteurs IA industrialises

Ce n'est pas encore une plateforme operateur de production, mais c'est deja une **V1 credible, demonstrable et extensible**.
