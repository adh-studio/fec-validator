# fec-validator

Contrôle d'un **Fichier des Écritures Comptables (FEC)** et export de la **balance générale**, en bibliothèque Python et en ligne de commande (`fec-check`).

> Ce projet n'est **pas** l'outil officiel de la DGFiP (« Test Compta Demat ») et ne le remplace pas. Il sert à repérer les anomalies le plus tôt possible, avant la remise du fichier. Voir la section [Limites](#limites).

## Le problème

Depuis 2014, toute entreprise qui tient sa comptabilité au moyen d'un système informatisé doit pouvoir remettre à l'administration fiscale, lors d'un contrôle, un FEC dont le format est fixé par l'article A47 A-1 du Livre des procédures fiscales : 18 colonnes dans un ordre imposé, dates au format `AAAAMMJJ`, montants avec une virgule décimale, écritures équilibrées, etc. Un fichier non conforme peut être rejeté et exposer l'entreprise à l'amende prévue à l'article 1729 D du CGI.

Dans la pratique, les exports produits par les logiciels comptables contiennent souvent des défauts : une écriture déséquilibrée après une reprise de données, un libellé vide, un montant exporté avec un point, un lettrage sans date, des écritures datées après la clôture. `fec-validator` lit le fichier en flux, applique une série de règles simples et indépendantes, et produit un rapport lisible (console) ou exploitable par un programme (JSON).

## Fonctionnalités

- Contrôle du nom de fichier `SirenFECAAAAMMJJ` : SIREN vérifié par l'algorithme de Luhn, date de clôture utilisée pour déduire l'exercice (surcharge possible avec `--debut` et `--fin`).
- Détection de l'encodage (UTF-8 avec ou sans BOM, sinon repli ISO-8859-15 ou Windows-1252) et du séparateur (tabulation ou `|`).
- Prise en charge des deux présentations des montants : `Debit` / `Credit`, ou `Montant` / `Sens` (`D`/`C`, ainsi que `+1`/`-1` rencontrés en pratique).
- 26 règles réparties en quatre portées : fichier, ligne, écriture (JournalCode + EcritureNum) et global. Chaque anomalie porte un code (`FEC-L003`), une gravité, un numéro de ligne et un message en français.
- Montants calculés en `decimal.Decimal` (jamais en flottant) : un centime d'écart est un centime d'écart.
- Lecture ligne à ligne : seuls des agrégats par écriture restent en mémoire. Le détail des anomalies est plafonné par règle (100 par défaut) alors que toutes les occurrences sont comptées.
- Rapport console (`rich`) ou JSON, codes retour exploitables en intégration continue.
- Balance générale par `CompteNum` (total débit, total crédit, solde), à l'écran ou en CSV compatible Excel.
- Registre de règles : ajouter un contrôle revient à écrire une petite classe.

## Installation

Le paquet n'est pas publié sur PyPI. Il s'installe depuis le dépôt Git :

```bash
# Comme outil en ligne de commande isolé, avec uv
uv tool install git+https://github.com/heniwizeup-dotcom/fec-validator.git

# Ou avec pip, dans un environnement virtuel
pip install git+https://github.com/heniwizeup-dotcom/fec-validator.git
```

Depuis une copie locale du dépôt :

```bash
uv sync                     # crée .venv avec les dépendances de développement
uv run fec-check --help
```

Python 3.11 ou plus récent est requis. Dépendances d'exécution : `typer` et `rich`.

## Utilisation en ligne de commande

```text
fec-check validate FICHIER [--debut AAAAMMJJ] [--fin AAAAMMJJ] [--format console|json]
                           [--max-anomalies N] [--ignorer CODE ...] [--strict]
fec-check balance FICHIER [-o balance.csv]
fec-check rules
```

| Code retour | Signification |
|---|---|
| `0` | aucune erreur (des avertissements peuvent exister) |
| `1` | au moins une erreur, ou un avertissement avec `--strict` |
| `2` | fichier illisible (absent, vide, binaire, UTF-16...) ou option invalide |

Les sorties ci-dessous ont été produites par l'outil sur les fichiers du dossier [`examples/`](examples/), avec une console de 100 colonnes sans couleur (`COLUMNS=100 NO_COLOR=1`). Seule la ligne « Durée » varie d'une exécution à l'autre.

### Fichier conforme

```text
$ fec-check validate examples/123456782FEC20251231.txt
┌─ Validation FEC : 123456782FEC20251231.txt ────────────────────────────────────────────┐
│ SIREN                123456782 (clé de contrôle valide)                                │
│ Date de clôture      31/12/2025                                                        │
│ Exercice             du 01/01/2025 au 31/12/2025 (début supposé : exercice de 12 mois) │
│ Encodage             UTF-8                                                             │
│ Séparateur           tabulation                                                        │
│ Format des montants  Debit / Credit                                                    │
│ Lignes analysées     10                                                                │
│ Écritures            4                                                                 │
│ Total débit          2 612,00                                                          │
│ Total crédit         2 612,00                                                          │
│ Durée                0,00 s                                                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
FICHIER CONFORME : 0 erreur(s), 0 avertissement(s)
$ echo $?
0
```

### Fichier avec anomalies

`examples/987654321FEC20251231.txt` est séparé par des `|` et contient volontairement une anomalie de chaque sorte (le SIREN 987654321 ne passe pas la clé de Luhn).

```text
$ fec-check validate examples/987654321FEC20251231.txt
┌─ Validation FEC : 987654321FEC20251231.txt ────────────────────────────────────────────┐
│ SIREN                987654321 (clé de contrôle invalide)                              │
│ Date de clôture      31/12/2025                                                        │
│ Exercice             du 01/01/2025 au 31/12/2025 (début supposé : exercice de 12 mois) │
│ Encodage             UTF-8                                                             │
│ Séparateur           barre verticale (|)                                               │
│ Format des montants  Debit / Credit                                                    │
│ Lignes analysées     15                                                                │
│ Écritures            7                                                                 │
│ Total débit          3 450,00                                                          │
│ Total crédit         3 540,00                                                          │
│ Durée                0,00 s                                                            │
└────────────────────────────────────────────────────────────────────────────────────────┘
Anomalies par règle

  Code       Gravité         Règle                                                         Nombre
 ─────────────────────────────────────────────────────────────────────────────────────────────────
  FEC-E001   ERREUR          Écriture déséquilibrée (débit différent du crédit)                 1
  FEC-E002   ERREUR          Plusieurs EcritureDate dans une même écriture                      1
  FEC-F002   ERREUR          SIREN invalide (clé de Luhn)                                       1
  FEC-G001   ERREUR          Total des débits différent du total des crédits                    1
  FEC-L002   ERREUR          Champ obligatoire vide                                             1
  FEC-L003   ERREUR          Date invalide (format AAAAMMJJ attendu)                            2
  FEC-L004   ERREUR          Montant mal formé (virgule décimale, sans séparateur de            1
                             milliers)
  FEC-L005   ERREUR          Débit et crédit renseignés sur la même ligne                       1
  FEC-L008   AVERTISSEMENT   EcritureLet renseigné sans DateLet                                 1
  FEC-L009   ERREUR          CompAuxNum renseigné sans CompAuxLib                               1
  FEC-L010   AVERTISSEMENT   Montantdevise et Idevise incohérents                               1
  FEC-L012   ERREUR          EcritureDate hors de l'exercice                                    2
  FEC-L014   AVERTISSEMENT   ValidDate antérieure à EcritureDate                                2

Détail

  Ligne   Code       Message
 ─────────────────────────────────────────────────────────────────────────────────────────────────
          FEC-F002   Le SIREN 987654321 du nom de fichier est invalide (la clé de contrôle de
                     Luhn ne correspond pas).
      2   FEC-E001   Écriture VT/VT0001 déséquilibrée : débit 1200,00, crédit 1190,00, écart
                     10,00 (3 lignes).
      5   FEC-L004   Debit '100.00' n'est pas un montant valide : le séparateur décimal doit être
                     la virgule.
      7   FEC-L009   Compte auxiliaire 'FRS001' sans libellé (CompAuxLib vide).
      9   FEC-L008   Lettrage 'A' sans date de lettrage (DateLet vide).
      9   FEC-E002   Écriture BQ/BQ0001 : EcritureDate '20250210' (ligne 8) et '20250211' (ligne
                     9).
     10   FEC-L003   EcritureDate '20250230' n'est pas une date valide au format AAAAMMJJ.
     11   FEC-L003   EcritureDate '20250230' n'est pas une date valide au format AAAAMMJJ.
     12   FEC-L002   Le champ obligatoire CompteLib est vide.
     12   FEC-L010   Idevise renseigné (USD) sans montant en devise (Montantdevise vide ou nul).
     14   FEC-L005   Débit (50,00) et crédit (50,00) sont tous deux non nuls sur la même ligne.
     15   FEC-L012   EcritureDate 15/01/2026 postérieure à la clôture de l'exercice (31/12/2025).
     15   FEC-L014   ValidDate 10/01/2026 antérieure à EcritureDate 15/01/2026.
     16   FEC-L012   EcritureDate 15/01/2026 postérieure à la clôture de l'exercice (31/12/2025).
     16   FEC-L014   ValidDate 10/01/2026 antérieure à EcritureDate 15/01/2026.
          FEC-G001   Total débit 3450,00 différent du total crédit 3540,00, écart -90,00 (hors 1
                     ligne(s) au montant illisible).

FICHIER NON CONFORME : 12 erreur(s), 4 avertissement(s)
$ echo $?
1
```

Les numéros de ligne sont ceux du fichier (l'en-tête est la ligne 1). Une ligne dont un montant est illisible est exclue des totaux : l'équilibre de son écriture n'est alors pas contrôlé, pour ne pas signaler deux fois la même cause.

### Sortie JSON

```text
$ fec-check validate examples/987654321FEC20251231.txt --format json
{
  "file": "examples\\987654321FEC20251231.txt",
  "valid": false,
  "fatal": false,
  "metadata": {
    "encoding": "utf-8",
    "separator": "pipe",
    "layout": "debit_credit",
    "siren": "987654321",
    "siren_valid": false,
    "closing_date": "2025-12-31",
    "period": {
      "start": "2025-01-01",
      "end": "2025-12-31",
      "start_inferred": true
    }
  },
  "statistics": {
    "lines": 15,
    "malformed_lines": 0,
    "entries": 7,
    "total_debit": "3450.00",
    "total_credit": "3540.00"
  },
  "summary": {
    "errors": 12,
    "warnings": 4,
    "by_rule": {
      "FEC-E001": 1,
      "FEC-E002": 1,
      "FEC-F002": 1,
      "FEC-G001": 1,
      "FEC-L002": 1,
      "FEC-L003": 2,
      "FEC-L004": 1,
      "FEC-L005": 1,
      "FEC-L008": 1,
      "FEC-L009": 1,
      "FEC-L010": 1,
      "FEC-L012": 2,
      "FEC-L014": 2
    },
    "max_issues_per_rule": 100,
    "truncated": false
  },
  "issues": [
    {
      "code": "FEC-F002",
      "severity": "error",
      "line": null,
      "column": null,
      "entry": null,
      "message": "Le SIREN 987654321 du nom de fichier est invalide (la clé de contrôle de Luhn ne correspond pas)."
    },
    ...
  ],
  "duration_seconds": 0.003
}
```

Les montants sont des chaînes pour ne perdre aucune précision. `summary.by_rule` compte toutes les occurrences, `issues` n'en détaille que les `max_issues_per_rule` premières par règle.

### Balance générale

```text
$ fec-check balance examples/123456782FEC20251231.txt
Balance générale

  CompteNum   CompteLib                       Débit     Crédit       Solde
 ──────────────────────────────────────────────────────────────────────────
  40100000    Fournisseurs                     0,00     212,00     -212,00
  41100000    Clients                      1 200,00   1 200,00        0,00
  44566000    TVA déductible                  20,00       0,00       20,00
  44571000    TVA collectée                    0,00     200,00     -200,00
  51200000    Banque                       1 200,00       0,00    1 200,00
  60400000    Achats de prestations           92,00       0,00       92,00
  60610000    Fournitures non stockables     100,00       0,00      100,00
  70600000    Prestations de services          0,00   1 000,00   -1 000,00

  Total                                    2 612,00   2 612,00        0,00

8 comptes, 10 lignes lues

$ fec-check balance examples/123456782FEC20251231.txt -o balance.csv
Balance générale écrite dans balance.csv
8 comptes, 10 lignes lues
```

Le CSV est encodé en UTF-8 avec BOM, séparé par `;`, avec des virgules décimales, pour s'ouvrir directement dans un Excel français. Le solde est positif quand le compte est débiteur :

```text
CompteNum;CompteLib;TotalDebit;TotalCredit;Solde
40100000;Fournisseurs;0,00;212,00;-212,00
41100000;Clients;1200,00;1200,00;0,00
44566000;TVA déductible;20,00;0,00;20,00
44571000;TVA collectée;0,00;200,00;-200,00
51200000;Banque;1200,00;0,00;1200,00
60400000;Achats de prestations;92,00;0,00;92,00
60610000;Fournitures non stockables;100,00;0,00;100,00
70600000;Prestations de services;0,00;1000,00;-1000,00
```

Les lignes illisibles (montant mal formé, mauvais nombre de champs) sont ignorées et comptées ; `fec-check validate` en donne le détail.

### Options utiles

- `--debut 20240701 --fin 20251231` : exercice de 18 mois, ou fichier dont le nom ne suit pas la norme.
- `--ignorer FEC-L008 --ignorer FEC-L014` : désactive des règles jugées non pertinentes pour un dossier.
- `--max-anomalies 20` : moins de détail à l'écran, les compteurs restent exacts.
- `--strict` : fait échouer la commande dès le premier avertissement (utile en CI).

## Utilisation en bibliothèque

```python
from fec_validator import compute_balance, validate

report = validate("examples/987654321FEC20251231.txt", max_issues_per_rule=20)
print(report.is_valid, report.error_count, report.warning_count)
for issue in report.issues[:3]:
    print(issue.code, issue.severity.value, issue.line, issue.message)

balance = compute_balance("examples/123456782FEC20251231.txt")
for account in balance.accounts[:3]:
    print(account.compte_num, account.compte_lib, account.debit, account.credit, account.solde)
```

Sortie :

```text
False 12 4
FEC-F002 error None Le SIREN 987654321 du nom de fichier est invalide (la clé de contrôle de Luhn ne correspond pas).
FEC-E001 error 2 Écriture VT/VT0001 déséquilibrée : débit 1200,00, crédit 1190,00, écart 10,00 (3 lignes).
FEC-L004 error 5 Debit '100.00' n'est pas un montant valide : le séparateur décimal doit être la virgule.
40100000 Fournisseurs 0.00 212.00 -212.00
41100000 Clients 1200.00 1200.00 0.00
44566000 TVA déductible 20.00 0.00 20.00
```

`validate()` accepte aussi `start=`, `end=` (objets `datetime.date`), `exclude=` (codes de règles) et lève `FecReadError` quand le fichier est illisible. `report.to_dict()` donne la structure JSON ci-dessus.

## Règles

Liste obtenue avec `fec-check rules`. Une **erreur** rend le fichier non conforme ; un **avertissement** signale un point à vérifier.

| Code | Gravité | Portée | Contrôle |
|---|---|---|---|
| FEC-F001 | avertissement | fichier | Nom de fichier non conforme (SIREN + FEC + AAAAMMJJ) |
| FEC-F002 | erreur | fichier | SIREN invalide (clé de Luhn) |
| FEC-F003 | erreur | fichier | Date de clôture du nom de fichier invalide |
| FEC-F004 | erreur (bloquante) | fichier | Séparateur de champs non reconnu (tabulation ou `\|`) |
| FEC-F005 | erreur (bloquante) | fichier | Colonnes obligatoires absentes de l'en-tête |
| FEC-F006 | erreur | fichier | Colonnes inattendues ou en double |
| FEC-F007 | erreur | fichier | Ordre des colonnes non conforme |
| FEC-F008 | avertissement | fichier | Casse des noms de colonnes différente de la norme |
| FEC-L001 | erreur | ligne | Nombre de champs différent de l'en-tête (les autres contrôles de la ligne sont alors ignorés) |
| FEC-L002 | erreur | ligne | Champ obligatoire vide : JournalCode, JournalLib, EcritureNum, EcritureDate, CompteNum, CompteLib, PieceRef, PieceDate, EcritureLib, ValidDate |
| FEC-L003 | erreur | ligne | Date invalide (format AAAAMMJJ, date calendaire réelle) |
| FEC-L004 | erreur | ligne | Montant mal formé (virgule décimale, sans séparateur de milliers) |
| FEC-L005 | erreur | ligne | Débit et crédit renseignés sur la même ligne |
| FEC-L006 | erreur | ligne | Sens invalide (D, C, +1 ou -1 attendu) |
| FEC-L007 | avertissement | ligne | Montant négatif dans Debit, Credit ou Montant |
| FEC-L008 | avertissement | ligne | EcritureLet renseigné sans DateLet |
| FEC-L009 | erreur | ligne | CompAuxNum renseigné sans CompAuxLib |
| FEC-L010 | avertissement | ligne | Montantdevise et Idevise incohérents (l'un sans l'autre) |
| FEC-L011 | avertissement | ligne | Idevise hors format ISO 4217 (trois lettres majuscules) |
| FEC-L012 | erreur | ligne | EcritureDate hors de l'exercice (après la clôture, ou avant un début donné par `--debut`) |
| FEC-L013 | avertissement | ligne | EcritureDate antérieure au début d'exercice supposé (12 mois) |
| FEC-L014 | avertissement | ligne | ValidDate antérieure à EcritureDate |
| FEC-E001 | erreur | écriture | Écriture déséquilibrée (débit différent du crédit) |
| FEC-E002 | erreur | écriture | Plusieurs EcritureDate dans une même écriture |
| FEC-G001 | erreur | global | Total des débits différent du total des crédits |
| FEC-G002 | avertissement | global | Aucune ligne d'écriture |

Une règle **bloquante** empêche d'interpréter les lignes : l'analyse s'arrête après l'en-tête.

### Choix de gravité à connaître

Lorsque la norme ou la pratique ne permettait pas de trancher avec certitude, la règle a été classée en avertissement plutôt qu'en erreur :

- **FEC-L008 (lettrage sans date)** : le lien entre EcritureLet et DateLet découle de la description des champs, mais de nombreux logiciels exportent un code de lettrage sans date. Classé en avertissement.
- **FEC-L010 et FEC-L011 (devises)** : beaucoup d'exports écrivent `0,00` dans Montantdevise sans devise, et les montants en devise sont souvent signés. Seules les incohérences nettes sont signalées, en avertissement.
- **FEC-L007 (montant négatif)** : la présentation attendue place un montant positif dans la colonne opposée, mais des montants négatifs (avoirs, extournes) se rencontrent et ne sont pas forcément rejetés.
- **FEC-L013 (début d'exercice supposé)** : sans `--debut`, l'exercice est supposé durer 12 mois. Un premier exercice peut être plus long : une date antérieure n'est donc qu'un avertissement tant que le début n'est pas donné explicitement (elle devient FEC-L012 avec `--debut`).
- **FEC-L014 (ValidDate avant EcritureDate)** et **FEC-F008 (casse des colonnes)** : points à vérifier, pas des non-conformités établies.
- **FEC-F001 (nom de fichier)** : le nom est souvent modifié lors d'un simple transfert ; le contenu reste contrôlé normalement.

À l'inverse, **FEC-L009** (compte auxiliaire sans libellé) est une erreur : la norme décrit CompAuxLib comme le libellé du compte auxiliaire, vide seulement si ce compte n'est pas utilisé.

## Architecture

```text
src/fec_validator/
├── reader.py        détection de l'encodage et du séparateur, lecture ligne à ligne
├── header.py        analyse de l'en-tête : présentation, colonnes absentes, ordre, casse
├── filename.py      nom SirenFECAAAAMMJJ, clé de Luhn, calcul de l'exercice
├── parsing.py       dates, montants Decimal, sens, formats français
├── columns.py       colonnes de la norme et colonnes obligatoires
├── models.py        Issue, Severity, Scope, FiscalPeriod, FecLine
├── context.py       contextes en lecture seule passés aux règles
├── rules/
│   ├── base.py      classes de base FileRule, LineRule, EntryRule, GlobalRule et registre
│   ├── file_rules.py, line_rules.py, entry_rules.py, global_rules.py
├── aggregation.py   agrégats par écriture et totaux, alimentés en flux
├── report.py        collecte plafonnée des anomalies, ValidationReport
├── validator.py     orchestration : une seule lecture du fichier
├── balance.py       balance générale et export CSV
├── renderers.py     rendu console (rich) et JSON
└── cli.py           commandes typer : validate, balance, rules
```

Déroulement de `validate()` :

1. le nom du fichier donne le SIREN et la clôture, d'où l'exercice ;
2. `FecReader` détecte l'encodage, lit l'en-tête et le séparateur ; les règles de fichier s'exécutent ;
3. chaque ligne est découpée, passe par les règles de ligne puis alimente l'`Aggregator` (débit, crédit et date par écriture, totaux) ;
4. en fin de lecture, les règles d'écriture parcourent les agrégats, puis les règles globales les totaux ;
5. l'`IssueCollector` compte tout mais ne conserve que les N premières anomalies de chaque règle.

La mémoire utilisée dépend donc du nombre d'écritures distinctes, pas du nombre de lignes.

## Ajouter une règle

Une règle est une classe décorée par `@register`. Le validateur la découvre via le registre ; la CLI l'affiche dans `fec-check rules` et accepte son code dans `--ignorer`.

```python
from collections.abc import Iterator

from fec_validator.context import ValidationContext
from fec_validator.models import FecLine, Issue, Severity
from fec_validator.rules import LineRule, register


@register
class CashAccountRule(LineRule):
    """Flag lines booked on cash accounts (class 53)."""

    code = "FEC-L901"
    severity = Severity.WARNING
    title = "Compte de caisse utilisé"

    def check(self, line: FecLine, ctx: ValidationContext) -> Iterator[Issue]:
        if line.get("CompteNum").startswith("53"):
            yield self.issue(
                "Écriture sur un compte de caisse.", line=line.number, column="CompteNum"
            )
```

Pour une règle intégrée au projet : placer la classe dans le module de sa portée (`rules/line_rules.py`...), choisir le code suivant de la série, ajouter des tests unitaires dans `tests/`, puis compléter le tableau ci-dessus. Les règles d'écriture reçoivent un `EntryAggregate`, les règles globales les `Totals`, les règles de fichier un `FileContext`.

## Performance

Mesure faite avec `scripts/benchmark.py`, qui génère un FEC synthétique équilibré puis le valide :

```bash
uv run python scripts/benchmark.py --lines 1000000 --dir bench
```

Machine : ordinateur portable Windows 11, Intel Core i5-11400H (6 cœurs, 2,7 GHz), 16 Go de RAM, SSD NVMe, Python 3.14.4. Fichier de 1 000 002 lignes (115 Mio, 333 048 écritures) :

| Mesure | Résultat |
|---|---|
| `validate()`, trois exécutions | 12,4 s, 33,2 s et 39,8 s |
| Mémoire maximale du processus (working set) | 225 Mio |
| `compute_balance()` | 4,9 s |
| Fichier de 100 001 lignes (33 304 écritures) | 1,3 s, 50 Mio |

L'écart entre les exécutions vient de la charge de la machine (la plus lente a tourné pendant d'autres traitements) ; le chiffre le plus favorable correspond à environ 80 000 lignes par seconde. La validation est mono-cœur. Ces mesures portent sur un fichier généré et sans anomalie ; elles donnent un ordre de grandeur, pas une garantie.

## Limites

- **Ce n'est pas l'outil officiel.** La DGFiP met à disposition « Test Compta Demat », qui reste la référence. `fec-validator` n'a pas été comparé systématiquement à cet outil et ne garantit pas qu'un fichier accepté ici le sera par l'administration.
- Seul le format « fichier à plat » avec séparateur (tabulation ou `|`) est traité : pas de format XML, pas de format à longueur fixe, pas de champs entre guillemets.
- Les règles portent sur la forme du fichier. Elles ne vérifient pas le fond : conformité des numéros de compte au plan comptable, continuité de la numérotation des écritures, ordre chronologique de validation, cohérence avec la liasse fiscale, présence des à-nouveaux, etc.
- Les champs propres à certains régimes (bénéfices non commerciaux, comptabilités de trésorerie, colonnes complémentaires) ne sont pas pris en charge ; une colonne en plus est signalée par FEC-F006.
- La détection de l'encodage est une heuristique : un fichier mono-octet est lu en Windows-1252 s'il contient des octets 0x80 à 0x9F, sinon en ISO-8859-15.
- La mémoire croît avec le nombre d'écritures distinctes (environ 225 Mio pour 333 000 écritures dans la mesure ci-dessus).
- Les messages et le rapport sont en français ; les identifiants du code et les clés JSON sont en anglais.

## Développement

```bash
uv sync                          # environnement et dépendances de développement
uv run pytest --cov              # tests et couverture (seuil 90 %)
uv run ruff check .              # lint
uv run ruff format --check .     # formatage
uv run mypy src                  # typage strict
```

Les tests génèrent leurs propres FEC synthétiques (`tests/fec_factory.py`) : fichier valide, chaque type d'anomalie, les deux séparateurs, les encodages UTF-8, UTF-8 avec BOM, Windows-1252 et ISO-8859-15, et la présentation Montant / Sens. Toutes les données sont fictives, y compris les SIREN (123456782 passe la clé de Luhn, 123456789 et 987654321 non). Un test vérifie que les deux fichiers d'exemple produisent toujours le résultat décrit ici.

L'intégration continue (`.github/workflows/ci.yml`) exécute ces commandes sous Ubuntu avec Python 3.11, 3.12 et 3.13.

## Licence

MIT, voir [LICENSE](LICENSE). Copyright (c) 2026 Henintsoa Andriamaholy.
