---
title: "Guide utilisateur — AI Delphi Council"
author: "AI Delphi Council"
lang: fr-FR
geometry: margin=2.2cm
fontsize: 11pt
---

# AI Delphi Council
## Guide utilisateur

**Version du guide : 1.0 — septembre 2026**  
**Produit : AI Delphi Council**

> AI Delphi Council consulte plusieurs modèles d’intelligence artificielle, organise une revue croisée anonymisée, puis produit une réponse de synthèse.

---

## 1. Découvrir AI Delphi Council

AI Delphi Council est un espace de travail collaboratif entre plusieurs modèles d’IA. Au lieu de dépendre d’une seule réponse, l’application confronte plusieurs points de vue et rend visibles les étapes du raisonnement collectif.

Le service fonctionne en trois étapes :

1. **Réponses individuelles** : chaque modèle propose sa propre réponse.
2. **Évaluation par les pairs** : les réponses sont comparées et classées anonymement.
3. **Synthèse du président** : le modèle désigné *Chairman* rassemble les meilleurs éléments dans une réponse finale.

Cette méthode est particulièrement utile pour analyser un sujet complexe, comparer des options, vérifier un plan ou obtenir plusieurs angles de vue avant de décider.

### À retenir

- Une réponse finale n’est pas une garantie de vérité : vérifiez les informations importantes.
- La diversité des modèles améliore généralement la qualité des perspectives.
- Les modèles locaux via LM Studio permettent de limiter l’envoi de données à des services externes.

---

## 2. Première connexion

### 2.1 Se connecter

1. Ouvrez AI Delphi Council.
2. Connectez-vous avec votre compte, selon le mode d’authentification proposé par votre organisation.
3. Acceptez les conditions d’utilisation lors du premier démarrage.
4. Vérifiez votre solde de crédits avant de lancer une requête.

Chaque requête au council consomme des crédits selon le barème défini par l’administrateur. Le coût peut être différent pour une requête standard et une requête utilisant des images ou l’analyse visuelle.

### 2.2 Créer une conversation

1. Cliquez sur **Nouvelle conversation** dans la barre latérale.
2. Saisissez votre question dans la zone de message.
3. Appuyez sur **Entrée** ou cliquez sur **Envoyer**.
4. Pour insérer un retour à la ligne sans envoyer, utilisez **Maj + Entrée**.

La première requête génère automatiquement un titre pour la conversation. Vos conversations précédentes restent accessibles dans la barre latérale.

---

## 3. Poser une bonne question

Pour obtenir une réponse exploitable :

- indiquez clairement votre objectif ;
- ajoutez le contexte, les contraintes et le public visé ;
- demandez un format précis : tableau, plan d’action, comparaison, résumé ou étapes ;
- précisez les critères de décision ;
- demandez aux modèles de signaler leurs incertitudes et leurs hypothèses.

### Exemple

> Compare les trois stratégies proposées dans le document joint pour une PME de 20 personnes. Classe-les selon le coût, le délai, les risques et la facilité de mise en œuvre. Termine par une recommandation argumentée et indique les informations manquantes.

---

## 4. Comprendre les trois étapes

### Étape 1 — Réponses individuelles

Les modèles du council répondent séparément à votre question. Chaque réponse est consultable dans un onglet identifié par le modèle utilisé.

Comparez notamment :

- les conclusions communes ;
- les désaccords ;
- les hypothèses différentes ;
- les sources ou exemples cités ;
- les points laissés sans réponse.

### Étape 2 — Revue et classement anonymisés

Chaque modèle reçoit les réponses et évalue la qualité des autres réponses sans connaître leur identité d’origine. Les réponses sont présentées sous des labels tels que **Response A**, **Response B** et **Response C** pendant l’évaluation.

L’interface affiche :

- le texte brut de chaque évaluation ;
- le classement extrait automatiquement ;
- le classement agrégé ;
- la position moyenne et le nombre de votes par réponse.

Les noms de modèles affichés dans l’interface servent à faciliter la lecture après la dé-anonymisation. L’évaluation initiale a été réalisée avec des labels anonymes.

> Le classement agrégé est un indicateur de consensus, pas une preuve qu’une réponse est exacte.

### Étape 3 — Synthèse finale

Le Chairman analyse les réponses individuelles et les évaluations, puis rédige une réponse unique. Lisez cette synthèse avec les réponses des étapes 1 et 2 lorsque la décision est sensible ou que les modèles sont en désaccord.

---

## 5. Utiliser des documents et des images

AI Delphi Council peut utiliser des fichiers comme contexte pour une question.

### Formats pris en charge

- PDF ;
- Word : `.doc`, `.docx` ;
- texte : `.txt`, `.md`, `.rtf` ;
- présentations : `.ppt`, `.pptx` ;
- images : `.png`, `.jpg`, `.jpeg`, `.gif`, `.webp`.

### Ajouter un document

1. Cliquez sur le bouton de téléchargement dans la zone de saisie, ou faites glisser les fichiers dans la zone de conversation.
2. Ouvrez le panneau **Documents** pour consulter la liste des fichiers.
3. Activez ou désactivez chaque document selon le contexte souhaité.
4. Vérifiez que l’option d’inclusion des documents est activée avant d’envoyer la question.

Un document désactivé reste disponible dans votre espace mais n’est pas ajouté au contexte de la requête.

### OCR et analyse visuelle

Les images peuvent être traitées par OCR afin d’extraire leur texte. Pour de meilleurs résultats :

- utilisez une image nette et suffisamment haute résolution ;
- photographiez le document à plat ;
- évitez les ombres, reflets et textes inclinés ;
- vérifiez l’extraction avant de vous appuyer sur une donnée importante.

L’utilisation d’images peut appliquer un coût de requête différent selon la configuration de votre instance.

---

## 6. Choisir les modèles

Dans les paramètres, vous pouvez sélectionner les modèles du council et le Chairman, selon les droits accordés à votre compte.

- Sélectionnez au moins **deux modèles** pour constituer un council.
- Le Chairman doit faire partie des modèles sélectionnés.
- Préférez des modèles complémentaires : raisonnement, rédaction, analyse technique ou vision.
- Un modèle plus performant en synthèse peut être choisi comme Chairman.

Les administrateurs peuvent gérer le catalogue, les fournisseurs et les paramètres avancés. Un utilisateur peut disposer d’un council personnel qui remplace la sélection globale par défaut.

---

## 7. Utiliser LM Studio

LM Studio permet d’exécuter des modèles localement, sans envoyer les requêtes correspondantes à OpenRouter.

### Configuration

1. Installez LM Studio depuis [lmstudio.ai](https://lmstudio.ai).
2. Téléchargez et chargez un modèle compatible.
3. Ouvrez l’onglet **Local Server** et démarrez le serveur.
4. Utilisez l’URL par défaut `http://localhost:1234/v1`, sauf configuration différente.
5. Activez CORS dans LM Studio si l’application le demande.
6. Dans AI Delphi Council, ouvrez **Paramètres → LM Studio**.
7. Saisissez l’URL du serveur pour le modèle concerné.
8. Cliquez sur **Tester la connexion**, puis enregistrez.

### Modes disponibles

- **OpenRouter** : modèles hébergés dans le cloud ;
- **LM Studio** : modèles exécutés localement ;
- **Hybride** : combinaison de modèles locaux et cloud.

Le mode local peut réduire les coûts et améliorer la confidentialité, mais les performances dépendent de la mémoire, du processeur et du GPU de votre ordinateur. Plusieurs serveurs peuvent être utilisés sur des ports différents.

---

## 8. Crédits et facturation

Une requête est débitée avant son exécution. Si le pipeline échoue après le débit, l’application prévoit un remboursement automatique.

Si votre solde est insuffisant :

1. la requête n’est pas exécutée ;
2. une fenêtre indique le coût requis et le solde disponible ;
3. ouvrez la page **Crédits** pour acheter ou gérer un pack, selon les options disponibles.

Le coût réel peut dépendre du nombre de modèles, du volume de texte, des images et des fournisseurs utilisés. Consultez le barème et les conditions de votre instance.

---

## 9. Gestion des conversations

Depuis la barre latérale, vous pouvez :

- créer une conversation ;
- sélectionner une conversation existante ;
- consulter son titre et son historique ;
- supprimer une conversation.

La suppression d’une conversation est une action destructive. Vérifiez son contenu avant de la confirmer.

---

## 10. Conseils de fiabilité et de confidentialité

- Ne saisissez pas de secrets, mots de passe ou clés privées dans une requête.
- Vérifiez les informations juridiques, médicales, financières et opérationnelles auprès d’une source compétente.
- Comparez les réponses individuelles lorsque la synthèse paraît trop affirmative.
- Contrôlez les citations, chiffres et dates : un modèle peut produire une information erronée ou inventée.
- Utilisez LM Studio pour les données qui doivent rester sur votre machine, après avoir confirmé la configuration du mode local.
- Les documents actifs peuvent être ajoutés au contexte des requêtes : désactivez-les lorsque ce n’est plus nécessaire.

Selon le déploiement, les conversations et documents peuvent être stockés localement ou dans l’infrastructure configurée par l’organisation. Demandez à votre administrateur où sont conservées les données.

---

## 11. Dépannage

### La requête ne démarre pas

- Vérifiez que vous êtes connecté.
- Consultez votre solde de crédits.
- Vérifiez que la conversation est bien sélectionnée.
- Actualisez la page puis réessayez.

### Aucun modèle ne répond

- Vérifiez la connexion réseau et la configuration du fournisseur.
- Pour OpenRouter, vérifiez la clé API, les crédits du compte fournisseur et les modèles sélectionnés.
- Pour LM Studio, vérifiez que le serveur est démarré, que l’URL est correcte et que CORS est activé.
- Demandez à l’administrateur de vérifier les journaux du serveur.

### Le document ne peut pas être importé

- Vérifiez que son extension est prise en charge.
- Essayez un fichier moins volumineux ou une version convertie en PDF/TXT.
- Pour une image, améliorez la netteté et le contraste.
- Vérifiez que le fichier n’est pas corrompu.

### Les classements semblent incomplets

Le classement est extrait du texte produit par les modèles. Consultez toujours le texte brut affiché dans l’étape 2 et signalez les formats non conformes à l’administrateur.

### L’application locale ne s’ouvre pas

Pour une installation Windows, vérifiez que les services sont démarrés et que les ports configurés ne sont pas déjà utilisés. L’API locale utilise généralement le port **8001** ; l’interface peut utiliser un autre port selon le mode de déploiement.

---

## 12. Raccourcis clavier

| Raccourci | Action |
|---|---|
| Entrée | Envoyer le message |
| Maj + Entrée | Insérer une nouvelle ligne |
| Ctrl + N | Créer une nouvelle conversation, si activé par votre installation |

---

## 13. Pour obtenir de l’aide

Lorsque vous contactez le support, indiquez :

- l’heure approximative du problème ;
- la conversation concernée ;
- le modèle ou le mode utilisé ;
- le type de fichier, sans joindre de données confidentielles ;
- le message d’erreur exact ;
- si le problème est reproductible.

N’envoyez jamais votre clé API dans une demande d’assistance.

---

## Annexe — Exporter ce guide en PDF

Ce fichier Markdown est la source éditable du guide. Pour produire un PDF avec Pandoc :

```bash
pandoc docs/guide-utilisateur-ai-delphi-council.md \
  --from markdown \
  --template eisvogel \
  --pdf-engine=xelatex \
  -o docs/guide-utilisateur-ai-delphi-council.pdf
```

Sans modèle personnalisé, utilisez :

```bash
pandoc docs/guide-utilisateur-ai-delphi-council.md \
  --pdf-engine=xelatex \
  -o docs/guide-utilisateur-ai-delphi-council.pdf
```

Le PDF généré doit être vérifié avant diffusion, notamment les liens, les accents, la pagination et le rendu des tableaux.
