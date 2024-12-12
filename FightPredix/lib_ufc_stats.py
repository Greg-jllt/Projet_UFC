"""
librairie qui recolte les statistiques des combattants sur le site UFC Stats afin de consolider les informations deja obtenues via le site de l'UFC

Développée par :
    - [Gregory Jaillet](https://github.com/Greg-jllt)
    - [Hugo Cochereau](https://github.com/hugocoche)
"""

from collections import Counter
from selenium.webdriver.common.by import By
from rapidfuzz import fuzz
from warnings import warn
from selenium import webdriver

import re
import pandas as pd


def _temp_dict_ufc_stats(cplt_name: str, rows) -> dict:
    """
    Fonction qui recolte les noms des combattants et leur ratio de similarité avec le nom complet car les noms des combattants sont souvent tronqués entre les sites

    Args:
        cplt_name (str): nom complet du combattant
        rows (list): liste des lignes de la page de recherche
    """
    return {
        fuzz.ratio(cplt_name, f"{first_name} {last_name}"): (first_name, last_name)
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
        prenom_cell = cells[0].text.strip()
        nom_cell = cells[1].text.strip()

        print(prenom_cell, nom_cell)

        if prenom_cell == prenom and nom_cell == nom:
            try:
                link = row.find_element(By.XPATH, ".//a")
                link.click()
            except:
                print(
                    "Aucun lien trouvé pour cette ligne, mais le combattant a été identifié."
                )
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


def _recolte_victoires(driver: webdriver.Chrome) -> list:
    """
    Fonction qui recolte le nombre de victoires du combattant

    Args:
        driver (webdriver.Chrome): driver de la page du combattant
    """

    resultats = driver.find_element(By.CSS_SELECTOR, "span.b-content__title-record")
    pattern = re.compile(r"(\d+)-(\d+)-(\d+)")
    return [int(val) for val in pattern.search(resultats.text).groups()]


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
                if finish.text.strip() in ["U-DEC", "S-DEC"]
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
            if finish.text.strip() in ["KO/TKO", "SUB", "U-DEC", "S-DEC"]
        ]
    )


def _traitement_metriques(driver: webdriver.Chrome) -> dict:
    """
    Fonction qui réuni et nettoie les métriques récoltées

    Args:
        driver (webdriver.Chrome): driver de la page du combattant
    """
    finishes = _collecteur_finish(driver)
    resultats = _recolte_victoires(driver)
    stats = _recolte_ufc_stats(driver)
    temp_dict = {
        "KO/TKO": finishes["KO/TKO"],
        "SUB": finishes["SUB"],
        "DEC": finishes["DEC"],
        "Win": resultats[0],
        "Losses": resultats[1],
        "Draws": resultats[2],
        **stats,
    }

    final_dict = _nettoyage_metriques(temp_dict)

    return final_dict


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
                if re.fullmatch(r"\d+\.\d+", value)  # string en float
                else (
                    float(value.rstrip("%")) / 100
                    if "%" in value  # pourcentage en float
                    else (
                        (feet * 12 + inches)
                        if re.fullmatch(
                            r"\d+'\s*\d+\"", value.strip()
                        )  # conversion taille en pouces # Bug sur fabio agu (6' 0")
                        and (feet := int(re.findall(r"\d+", value)[0]))
                        and (inches := int(re.findall(r"\d+", value)[1]))
                        else (
                            float(value.rstrip(" lbs."))
                            if " lbs." in value.strip()
                            else (
                                int(value.rstrip('"'))
                                if re.fullmatch(r"\d+\"", value)
                                else None if value == "--" else value
                            )
                        )
                    )
                )
            )
            if isinstance(value, str)
            else value
        )
        for key, value in temp_dict.items()
    }


def _integration_metriques(
    data: pd.DataFrame, cplt_name: str, driver: webdriver.Chrome
) -> pd.DataFrame:
    """
    Fonction qui integre les metriques recoltees dans le dictionnaire

    Args:
        data (pd.DataFrame): dataframe contenant les informations des combattants
        cplt_name (str): nom complet du combattant
        driver (webdriver.Chrome): driver de la page du combattant
    """

    dictio = _traitement_metriques(driver)

    mapping = {
        "HEIGHT": "La Taille",
        "WEIGHT": "Poids",
        "REACH": "Reach",
        "STANCE": "Style de combat",
        "DOB": "Âge",
        "SLpM": "sig_str_head",
        "Str. Acc.": "sig_str_body",
        "SApM": "sig_str_leg",
        "Str. Def": "Précision_saisissante",
        "TD Acc.": "Précision_de_Takedown",
        "TD Avg.": "Sig. Str. A atterri",
        "TD Def.": "Sig. Frappes Encaissées",
        "Sub. Avg.": "Takedown avg",
        "Sub. Avg.": "Envoi avg",
        "Str. Def.": "Sig. Str.défense",
        "TD Def.": "Défense de démolition",
        "Knockdown Avg": "Knockdown Avg",
        "Fight Time": "Temps de combat moyen",
    }

    if cplt_name in data["Name"].values:

        combattant_row = data[data["Name"] == cplt_name].index[0]

        for key, value in dictio.items():
            if key in mapping.keys():
                data_key = mapping[key]
            else:
                data_key = key

            if pd.isna(data.loc[combattant_row, data_key]) or (
                data.loc[combattant_row, data_key] < value
                if isinstance(value, (int, float))
                and data_key in ["Win", "Losses", "Draws"]
                else False
            ):
                data.loc[combattant_row, data_key] = value

    return data


def cherche_combattant_UFC_stats(data : pd.DataFrame, driver : webdriver.Chrome) -> pd.DataFrame:
    """
    Fonction qui recolte les statistiques des combattants sur le site UFC Stats

    Args:
        data (pd.DataFrame): dataframe contenant les informations des combattants
        driver (webdriver.Chrome): driver de la page du combattant
    """

    for cplt_name, nickname in zip(data["Name"], data["Nickname"]):
        prenom, nom = cplt_name.split(" ")

        url = f"http://www.ufcstats.com/statistics/fighters/search?query={nom.lower()}"
        driver.get(url)

        for clé in [prenom, nickname]:
            if clé is not None:
                rows = driver.find_elements(
                    By.CSS_SELECTOR, "tbody > tr.b-statistics__table-row"
                )
                rows_count = len(rows)
                if rows_count >= 2:
                    break
                url = f"http://www.ufcstats.com/statistics/fighters/search?query={clé}"
                driver.get(url)
        else:
            warn(f"Le combattant {cplt_name} n'a pas été trouvé")
            break

        temp_dict = _temp_dict_ufc_stats(cplt_name, rows)

        _accès_cbt_page(temp_dict, driver)

        data = _integration_metriques(data, cplt_name, driver)

    driver.quit()

    return data


if __name__ == "__main__":
    ...
