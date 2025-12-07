# TP Kubernetes - Cours Data DevOps - Enseirb-Matmeca

Installer git-lfs avant de cloner le repo pour pouvoir telecharger le fichier de données :

```bash
brew install git-lfs
git lfs install
git clone git@github.com:rqueraud/cours_kubernetes.git
```

Placez le fichier `service-account.json`à la racine du projet.

Pour builder les images : 
```bash
docker build -t 2024_kubernetes_post_pusher -f ./post_pusher/Dockerfile .
docker build -t 2024_kubernetes_post_api -f ./post_api/Dockerfile .
```

Pour executer les images :
```bash
docker run 2024_kubernetes_post_pusher
docker run -p 8000:8000 2024_kubernetes_post_api
```

## Commandes utiles 

```bash
kind create cluster --config ./kind/config.yaml
kind get clusters  # Vérifie qu'il existe bien un cluster kind
kind load docker-image my_image

k9s -n cours-kubernetes # Controller l'état du déploiement kubernetes

kubectl create ns cours-kubernetes  # Créer un namespace
kubectl apply -n cours-kubernetes -f my_file.yaml

kubectl delete all -n cours-kubernetes --all  # Supprime tout dans le namespace
```