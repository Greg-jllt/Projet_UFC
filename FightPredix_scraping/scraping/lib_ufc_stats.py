"""
librairie qui recolte les statistiques des combattants sur le site UFC Stats afin de consolider les informations deja obtenues via le site de l'UFC

Développée par :
    - [Gregory Jaillet](https://github.com/Greg-jllt)
    - [Hugo Cochereau](https://github.com/hugocoche)
"""

from collections import Counter
from selenium.webdriver.common.by import By
from rapidfuzz import fuzz
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from rich.console import Console
from datetime import datetime

from .outils import configure_logger

import re
import pandas as pd
import traceback

date = datetime.now().strftime("%Y-%m-%d")
logger = configure_logger(f"{date}_crawler_UFC_stats")


def _temp_dict_ufc_stats(cplt_name: str, rows) -> dict:
    """
    Fonction qui recolte les noms des combattants et leur ratio de similarité avec le nom complet car les noms des combattants sont souvent tronqués entre les sites

    Args:
        cplt_name (str): nom complet du combattant
        rows (list): liste des lignes de la page de recherche
    """
    return {
        fuzz.ratio(cplt_name.lower(), f"{first_name.lower()} {last_name.lower()}"): (
            first_name,
            last_name,
        )
        for row in rows
        for tds in [
            row.find_elements(By.CSS_SELECTOR, "a.b-link.b-link_style_black[href]")
        ]
        if len(tds) >= 2
        for first_name, last_name in [(tds[0].text.strip(), tds[1].text.strip())]
    }


def _accès_cbt_page(temp_dict: dict, driver: webdriver.Chrome) -> None:
    """
    Fonction qui accède à la page du combattant ayant le ratio de similarité le plus élevé

    Args:
        temp_dict (dict): dictionnaire des ratios de similarité et des noms des combattants
        driver (webdriver.Chrome): driver de la page du combattant
    """
    max_ratio = max(temp_dict.keys())

    prenom, nom = temp_dict[max_ratio][0], temp_dict[max_ratio][1]

    rows = driver.find_elements(By.CSS_SELECTOR, "tr.b-statistics__table-row")

    for row in rows[2:]:

        cells = row.find_elements(By.XPATH, "./td")
        prenom_cell = cells[0].text.strip() if len(cells) > 0 else ""
        nom_cell = cells[1].text.strip() if len(cells) > 1 else ""

        if (prenom_cell == prenom or not prenom) and (nom_cell == nom or not nom):
            try:
                link = row.find_element(By.XPATH, ".//a").get_attribute("href")
                driver.get(link)
            except Exception:
                logger.error(f"Aucun lien n'a été trouvé pour {prenom} {nom}")
            break


def _recolte_ufc_stats(driver: webdriver.Chrome) -> dict:
    """
    Fonction qui recolte les statistiques des combattants

    Args:
        driver (webdriver.Chrome): driver de la page du combattant
    """
    liste_items = driver.find_elements(By.CSS_SELECTOR, "li.b-list__box-list-item")

    return {
        item.find_element(By.CSS_SELECTOR, "i.b-list__box-item-title")
        .text.strip(): item.text.replace(
            item.find_element(By.CSS_SELECTOR, "i.b-list__box-item-title").text.strip(),
            "",
        )
        .strip()
        for item in liste_items
        if item.text.strip()
    }


def _recolte_victoires(driver: webdriver.Chrome) -> list | None:
    """
    Fonction qui recolte le nombre de victoires du combattant

    Args:
        driver (webdriver.Chrome): driver de la page du combattant
    """

    resultats = driver.find_element(By.CSS_SELECTOR, "span.b-content__title-record")
    pattern = re.compile(r"(\d+)-(\d+)-(\d+)")
    match = pattern.search(resultats.text)
    match = pattern.search(resultats.text)
    if match:
        return [int(val) for val in pattern.search(resultats.text).groups()]  # type: ignore
    else:
        return None


def _vic_draws_losses_autres_parcours(
    driver: webdriver.Chrome, win_draw_loss: list
) -> dict | None:
    """
    Fonction qui recolte les victoires, les défaites et les matchs nuls des combattants de leurs autres parcours en soustrayant les victoires, les défaites et les matchs nuls du site UFC.com aux victoires, défaites et matchs nuls du site UFC Stats
    """
    resultats = _recolte_victoires(driver)

    return {
        "WIN_HP": int(resultats[0] - win_draw_loss[0]) if resultats else None,
        "LOSSES_HP": int(resultats[1] - win_draw_loss[1]) if resultats else None,
        "DRAWS_HP": int(resultats[2] - win_draw_loss[2]) if resultats else None,
    }


def _collecteur_finish(driver: webdriver.Chrome) -> Counter:
    """
    Fonction qui recolte les types de finitions des combattants

    Args:
        driver (webdriver.Chrome): driver de la page du combattant
    """
    return Counter(
        [
            (
                finish.text[2:5].strip()
                if finish.text.strip() in ["U-DEC", "S-DEC", "M-DEC"]
                else finish.text.strip()
            )
            for row in driver.find_elements(
                By.CSS_SELECTOR,
                "tr.b-fight-details__table-row.b-fight-details__table-row__hover.js-fight-details-click",
            )
            if (result := row.find_element(By.CSS_SELECTOR, "i.b-flag__text"))
            and result.text.strip().lower() == "win"
            for finish in row.find_elements(
                By.CSS_SELECTOR,
                "td.b-fight-details__table-col.l-page_align_left > p.b-fight-details__table-text",
            )
            if finish.text.strip()
            in ["KO/TKO", "SUB", "U-DEC", "S-DEC", "CNC", "DQ", "M-DEC", "Overturned"]
        ]
    )


def _traitement_metriques(driver: webdriver.Chrome, win_draw_loss: list) -> dict:
    """
    Fonction qui réuni et nettoie les métriques récoltées

    Args:
        driver (webdriver.Chrome): driver de la page du combattant
    """
    finishes = _collecteur_finish(driver)
    resultats_HP = _vic_draws_losses_autres_parcours(driver, win_draw_loss)
    stats = _recolte_ufc_stats(driver)

    temp_dict = {
        "KO/TKO": finishes["KO/TKO"],
        "SUB": finishes["SUB"],
        "DEC": finishes["DEC"],
        "WIN": int(win_draw_loss[0]),
        "LOSSES": int(win_draw_loss[1]),
        "DRAWS": int(win_draw_loss[2]),
        **resultats_HP,  # type: ignore
        **stats,  # type: ignore
    }

    final_dict = _nettoyage_metriques(temp_dict)

    logger.info(f"Metriques recoltees : {final_dict}")

    return final_dict


def _convertisseur_taille(taille: str) -> float | None:
    """
    Fonction qui convertit la taille en pouces

    Args:
        taille (str): taille du combattant
    """
    if match := re.match(r"(\d+)' (\d+)", taille.strip()):
        pieds, pouces = int(match.group(1)), int(match.group(2))
        return pieds * 12 + pouces
    return None


def _nettoyage_metriques(temp_dict: dict) -> dict:
    """
    Nettoie les metriques recoltees

    Args:
        temp_dict (dict): dictionnaire des metriques recoltees
    """
    return {
        key.rstrip(":") if ":" in key else key: (
            (
                float(value)
                if re.fullmatch(r"\d+\.\d+", value)
                else (
                    float(value.rstrip("%")) / 100
                    if "%" in value
                    else (
                        _convertisseur_taille(value)
                        if re.match(r"(\d+)' (\d+)", value.strip())
                        else (
                            float(value.rstrip(" lbs."))
                            if " lbs." in value.strip()
                            else (
                                int(value.rstrip('"'))
                                if re.fullmatch(r"\d+\"", value)
                                else (None if value == "--" else value)
                            )
                        )
                    )
                )
            )
            if isinstance(
                value, str
            )  # Appliquer le traitement si la valeur est une chaîne
            else value  # Sinon retourner la valeur telle quelle
        )
        for key, value in temp_dict.items()
    }


def _integration_metriques(
    data: pd.DataFrame, cplt_name: str, driver: webdriver.Chrome, win_draw_loss: list
) -> pd.DataFrame:
    """
    Fonction qui integre les metriques recoltees dans le dictionnaire

    Args:
        data (pd.DataFrame): dataframe contenant les informations des combattants
        cplt_name (str): nom complet du combattant
        driver (webdriver.Chrome): driver de la page du combattant
    """

    dictio = _traitement_metriques(driver, win_draw_loss)

    mapping = {
        "HEIGHT": "LA TAILLE",
        "WEIGHT": "POIDS",
        "REACH": "REACH",
        "STANCE": "STYLE DE COMBAT",
        "Str. Acc.": "PRÉCISION SAISISSANTE",
        "TD Acc.": "PRÉCISION DE TAKEDOWN",
        "SLpM": "SIG. STR. A ATTERRI",
        "SApM": "SIG. FRAPPES ENCAISSÉES",
        "TD Avg.": "TAKEDOWN AVG",
        "Sub. Avg.": "ENVOI AVG",
        "Str. Def": "SIG. STR.DÉFENSE",
        "TD Def.": "DÉFENSE DE DÉMOLITION",
    }

    try:
        if cplt_name in data["NAME"].values:

            combattant_row = data[data["NAME"] == cplt_name].index[0]

            for key, value in dictio.items():
                data_key = mapping.get(key, key)

                if data_key not in data.columns:
                    data[data_key] = None

                if pd.isna(data.loc[combattant_row, data_key]) or (
                    data.loc[combattant_row, data_key] < value
                    if isinstance(value, (int, float))
                    else False
                ):
                    data.loc[combattant_row, data_key] = value
    except Exception as e:
        logger.warning(f"Erreur lors de la recherche du combattant {cplt_name} : {e}")
        logger.error(traceback.format_exc())

    return data


def _cherche_combattant_UFC_stats(
    data: pd.DataFrame, driver: webdriver.Chrome
) -> pd.DataFrame:
    """
    Fonction qui recolte les statistiques des combattants sur le site UFC Stats

    Args:
        data (pd.DataFrame): dataframe contenant les informations des combattants
        driver (webdriver.Chrome): driver de la page du combattant
    """
    logger.info("Recherche des combattants sur le site UFC Stats")

    for cplt_name, nickname in zip(data["NAME"], data["NICKNAME"]):
        logger.info(f"combattant {cplt_name}")
        try:
            parts = cplt_name.split(" ")
            prenom, nom = parts[0], parts[1] if len(parts) > 1 else ""

            url = f"http://www.ufcstats.com/statistics/fighters/search?query={nom.lower()}"
            driver.get(url)

            for clé in [prenom, nickname]:
                rows = driver.find_elements(
                    By.CSS_SELECTOR, "tbody > tr.b-statistics__table-row"
                )
                if len(rows) >= 2:
                    break
                if clé is not None:
                    url = f"http://www.ufcstats.com/statistics/fighters/search?query={clé.lower()}"
                    driver.get(url)
            else:
                logger.warning(f"Le combattant {cplt_name} n'a pas été trouvé")
                continue

            temp_dict = _temp_dict_ufc_stats(cplt_name, rows)

            _accès_cbt_page(temp_dict, driver)

            win_draw_loss = data.loc[
                data["NAME"] == cplt_name, ["WIN", "LOSSES", "DRAWS"]
            ].values[0]

            data = _integration_metriques(data, cplt_name, driver, win_draw_loss)
        except Exception as e:
            logger.warning(
                f"Erreur lors de la recherche du combattant {cplt_name} : {e}"
            )
            logger.error(traceback.format_exc())
            continue

    return data


if __name__ == "__main__":

    Data = pd.read_csv("data/Data_jointes.csv")

    chrome_options = Options()

    chrome_options.add_argument("--headless")

    driver = webdriver.Chrome(options=chrome_options)

    Data2 = _cherche_combattant_UFC_stats(data=Data, driver=driver)

    Data.update(Data2)

    Data.to_csv("data/Data_jointes.csv", index=False)
