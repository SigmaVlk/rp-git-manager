# shgit

Lehká terminálová aplikace (TUI) pro práci s Git repozitáři přímo z příkazové řádky.

## Funkce

* Navigace v repozitáři pomocí klávesových zkratek
* Okamžité obnovení stavu repozitáře
* Zobrazení a přepínání logu příkazů
* Jednoduché, rychlé a minimalistické rozhraní

## Struktura projektu

```id="p9x2lm"
.
├── pyproject.toml
├── README.md
└── src
    └── shgit
        ├── app.py           # Hlavní TUI aplikace
        ├── git_service.py   # Logika pro práci s Gitem
        ├── widgets.py       # UI komponenty
        ├── styles.tcss      # Styly aplikace
        ├── __main__.py      # Vstupní bod
        └── __init__.py
```

## Instalace

```bash id="q2n8vk"
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Použití

Spusť aplikaci v libovolném Git repozitáři:

```bash id="8u3j1h"
shgit
```

## Klávesové zkratky

| Klávesa | Akce               | Popis                   |
| ------- | ------------------ | ----------------------- |
| q       | quit               | Ukončit aplikaci        |
| r       | refresh            | Obnovit stav repozitáře |
| j       | down               | Posun dolů              |
| k       | up                 | Posun nahoru            |
| @       | toggle_command_log | Přepnout log příkazů    |

## Vývoj

Projekt je rozdělen do několika částí:

* **app.py** – Správa běhu aplikace a UI
* **git_service.py** – Zapouzdření Git operací
* **widgets.py** – Vlastní UI komponenty
* **styles.tcss** – Definice stylů

## Požadavky

* Python 3.10+
* Git nainstalovaný a dostupný v PATH

## Licence

MIT (nebo jiná dle tvého výběru)

---

## Poznámky

* Ujisti se, že spouštíš `shgit` uvnitř platného Git repozitáře.
* Aplikace je navržená pro rychlost a jednoduchost, ne pro plné pokrytí všech Git funkcí.
