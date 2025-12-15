# README — DevOps Data TP (Kafka → Consumer → BigQuery + MongoDB) sur GKE

Equipe: Karim Mkaouar - Hassen Akrout

Ce dépôt met en place une chaîne **post-pusher → Kafka → post-consumer → (BigQuery + MongoDB)**, déployée automatiquement sur **GKE** via une pipeline **GitHub Actions** + images dans **GitHub Container Registry (GHCR)**.

## 1) Architecture cible

- **post-pusher** : publie des messages (posts) **dans Kafka** (pas d’écriture directe BigQuery).
- **post-consumer** : lit Kafka et fait l’écriture **dans BigQuery + MongoDB**.
- **post-api** : expose une API de lecture (actuellement via BigQuery).
- **MongoDB** : base persistante dans le cluster via **StatefulSet**.
- **Kafka** : broker + service + UI (accès via host/ports).

---

## 2) ConfigMap + Secret pour post-consumer (et paramètres Kafka UI)

### 2.1 Consumer ConfigMap
Le consumer est paramétré via ConfigMap (bootstrap Kafka, topic, dataset/table BigQuery, etc.).

Fichier : [`k8s-post-consumer-configmap.yaml`](k8s-post-consumer-configmap.yaml)

Exemples de clés typiques :
- `KAFKA_HOST` (ex: `kafka-broker-service.cours-kubernetes:9092`)
- `TOPIC` (ex: `posts`)
- `GROUP_ID` (important pour le scaling)
- `DATASET_ID` / `TABLE_ID`

### 2.2 Consumer Secrets
Les secrets du consumer sont séparés dans un Secret dédié.

Fichier : [`k8s-post-consumer-secret.yaml`](k8s-post-consumer-secret.yaml)

Le consumer utilise aussi :
- le secret GCP **service account** monté en volume (voir [`k8s-secret.yaml`](k8s-secret.yaml))
- le secret MongoDB (voir [`k8s-mongodb.yaml`](k8s-mongodb.yaml))

### 2.3 Paramètres Kafka UI (host + ports)
Les paramètres pour accéder à Kafka UI dépendent du Service déployé dans [`cours_kafka/kafka/service.yaml`](cours_kafka/kafka/service.yaml).

Commandes utiles :
```bash
kubectl -n cours-kubernetes get svc
kubectl -n cours-kubernetes describe svc <kafka-ui-service-name>
```

Accès (local) via port-forward (exemple) :
```bash
kubectl -n cours-kubernetes port-forward svc/<kafka-ui-service-name> 8080:<port-ui>
# puis ouvrir http://localhost:8080
```

---

## 3) Création du cluster GKE + authentification

### 3.1 Création du cluster (GKE Autopilot)
Nous utilisons un cluster GKE Autopilot (région `europe-west1`) et nous avons attribué, dans `IAM`, le rôle `Administrateur de Kubernetes Engine` au compte de service utilisé pour le déploiement.

Variables utilisées dans la pipeline : [`.github/workflows/pipeline.yaml`](.github/workflows/pipeline.yaml)
- `GCP_PROJECT_ID`
- `GKE_CLUSTER`
- `GKE_LOCATION`

### 3.2 Connexion gcloud (local)
```bash
gcloud auth login
gcloud config set project <GCP_PROJECT_ID>
gcloud container clusters get-credentials <GKE_CLUSTER> --region <GKE_LOCATION>
kubectl get nodes
```

### 3.3 Secrets GitHub nécessaires
Dans GitHub → **Settings → Secrets and variables → Actions**, on a ajouté :

- `GCP_SA_KEY` : JSON du service account (clé) utilisé par GitHub Actions
- (optionnel) autres secrets applicatifs selon le projet

### 3.4 Donner les droits Kubernetes au Service Account (RBAC)
Le service account utilisé par GitHub Actions doit pouvoir déployer dans le cluster.
En pratique, il faut des permissions de type **admin** sur le cluster/namespace.

Conceptuellement :
- créer/choisir un service account GCP dédié au CI/CD
- lui donner des rôles GKE adaptés (accès cluster + déploiement)
- côté cluster, s’assurer qu’il peut faire `kubectl apply`, `kubectl set image`, `kubectl rollout status`, etc.

---

## 4) Consumer : écriture BigQuery + MongoDB

### 4.1 BigQuery
Le consumer écrit en streaming dans BigQuery via `insert_rows_json`.
Code : [`cours_kafka.post_consumer.main`](cours_kafka/post_consumer/main.py)

Le dataset/table sont configurés via env vars :
- `DATASET_ID=data_devops`
- `TABLE_ID=posts`

### 4.2 MongoDB via StatefulSet
MongoDB est déployé dans le cluster en StatefulSet (stockage persistant via PVC).

Fichier : [`k8s-mongodb.yaml`](k8s-mongodb.yaml)
- Secret `mongodb-secret`
- Service `mongodb` + service headless `mongodb-headless`
- StatefulSet `mongodb`
- `volumeClaimTemplates` (PVC)

Déploiement manuel :
```bash
kubectl create ns cours-kubernetes
kubectl -n cours-kubernetes apply -f k8s-mongodb.yaml
kubectl -n cours-kubernetes rollout status statefulset/mongodb --timeout=600s
```

### 4.3 Tester que les données existent dans MongoDB
#### Option A : exec dans le pod Mongo
```bash
kubectl -n cours-kubernetes get pods -l app=mongodb
kubectl -n cours-kubernetes exec -it mongodb-0 -- mongosh -u root -p root --authenticationDatabase admin
```

Exemples de commandes `mongosh` :
```js
use data_devops
db.posts.countDocuments()
db.posts.findOne()
```

### 4.4 Tester que les données existent dans BigQuery
Dans GCP (console BigQuery), vérifier la table :
- `<project>.data_devops.posts`

Ou via CLI (si configuré) :
```bash
bq query --use_legacy_sql=false 'SELECT COUNT(*) AS c FROM `'<project>'.data_devops.posts`'
```
### Accéder à `post-api` (port-forward)

Par défaut, `post-api` n'est pas exposé en public sur GKE. Pour y accéder depuis ton PC, utilise un **port-forward** :

```bash
kubectl -n cours-kubernetes port-forward deploy/post-api 8000:8000
```

Ensuite, ouvre dans ton navigateur (ou via curl) :
- `http://localhost:8000/` (endpoint test)
- `http://localhost:8000/docs` (documentation Swagger FastAPI)

### Endpoints disponibles (`post_api/main.py`)

- `GET /` → renvoie `{ "Hello": "World" }`
- `GET /posts/{post_id}` → récupère un post depuis BigQuery à partir de son `id`
   - exemple : `http://localhost:8000/posts/123`
   
---

## 5) Pipeline CI/CD (GitHub Actions) : build → push GHCR → deploy GKE

Pipeline : [`.github/workflows/pipeline.yaml`](.github/workflows/pipeline.yaml)

### 5.1 Build & Push des images dans GitHub Container Registry
La pipeline build et push :
- `ghcr.io/<user>/post-pusher:<sha>`
- `ghcr.io/<user>/post-api:<sha>`
- `ghcr.io/<user>/post-consumer:<sha>`

### 5.2 Déploiement sur GKE
La pipeline :
1. s’authentifie à GCP (`google-github-actions/auth@v2`)
2. récupère les credentials du cluster (`get-gke-credentials@v2`)
3. applique les manifests k8s :
   - namespace
   - MongoDB (`k8s-mongodb.yaml`)
   - secrets/configmaps
   - Kafka (deployment/service)
   - apps (pusher/consumer/api)
4. met à jour les images via `kubectl set image`
5. attend les rollouts

---

## 6) Commandes utiles

Etat du namespace :
```bash
kubectl get ns
kubectl -n cours-kubernetes get pods -o wide
kubectl -n cours-kubernetes get svc
```

Logs :
```bash
kubectl -n cours-kubernetes logs deploy/post-pusher --tail=200
kubectl -n cours-kubernetes logs deploy/post-consumer --tail=200
kubectl -n cours-kubernetes logs deploy/post-api --tail=200
```

Rollout :
```bash
kubectl -n cours-kubernetes rollout status deploy/post-consumer --timeout=600s
kubectl -n cours-kubernetes rollout status statefulset/mongodb --timeout=600s
```



---

## 7) Fichiers principaux

- Pipeline : [`.github/workflows/pipeline.yaml`](.github/workflows/pipeline.yaml)
- MongoDB : [`k8s-mongodb.yaml`](k8s-mongodb.yaml)
- Consumer : [`k8s-post-consumer.yaml`](k8s-post-consumer.yaml), [`k8s-post-consumer-configmap.yaml`](k8s-post-consumer-configmap.yaml), [`k8s-post-consumer-secret.yaml`](k8s-post-consumer-secret.yaml), code [`cours_kafka.post_consumer.main`](cours_kafka/post_consumer/main.py)
- Pusher : [`k8s-post-pusher.yaml`](k8s-post-pusher.yaml), code [`post_pusher.main`](post_pusher/main.py)
- API : [`k8s-post-api.yaml`](k8s-post-api.yaml), code [`post_api.main`](post_api/main.py)
- Kafka : [`cours_kafka/kafka/deployment.yaml`](cours_kafka/kafka/deployment.yaml), [`cours_kafka/kafka/service.yaml`](cours_kafka/kafka/service.yaml)