"""
Processus de scraping des données sur les sites UFC.com, UFC stats et Tapology.
Construction de la base de données récapitulant les combats de l'UFC et les informations des combattants.
"""

from .lib_front_page import _page_principal_UFC
from .lib_combats import _main_combat_recolte
from .lib_ufc_stats import _cherche_combattant_UFC_stats
from .lib_constructeur import _main_construct
from .outils import configure_logger
from datetime import datetime
from selenium.webdriver.chrome.options import Options
from selenium import webdriver

import pandas as pd
import subprocess
import os


date = datetime.now().strftime("%Y-%m-%d")
logger = configure_logger(f"{date}_crawler_scraping")


def Dataframe_caracteristiques(driver: webdriver.Chrome) -> pd.DataFrame:
    Data = _page_principal_UFC(main_driver=driver)

    return Data


def Dataframe_caracteristiques_ufc_stats(
    data: pd.DataFrame, driver: webdriver.Chrome
) -> pd.DataFrame:
    Data = _cherche_combattant_UFC_stats(data=data, driver=driver)

    return Data


def Dataframe_combats(driver: webdriver.Chrome) -> pd.DataFrame:
    Data = _main_combat_recolte(driver=driver)

    return Data


def _constructeur(Data: pd.DataFrame, combats: pd.DataFrame) -> pd.DataFrame:
    combats, Data = _main_construct(combats, Data)

    return combats, Data


def main():
    chrome_options = Options()

    chrome_options.add_argument("--headless")

    main_driver = webdriver.Chrome(options=chrome_options)

    logger.info("Lancement du scraping sur UFC.com")
    Data = Dataframe_caracteristiques(main_driver)

    main_driver = webdriver.Chrome(options=chrome_options)

    logger.info("Lancement du scraping sur UFC stats")
    Data = Dataframe_caracteristiques_ufc_stats(Data, main_driver)

    Data.to_csv("data/Data_ufc_fighters.csv", index=False)

    # logger.info("Lancement du scraping sur tapology et création des données jointes")
    # subprocess.run(
    #     ["python", "-m", "FightPredix_scraping.scraping.lib_join_ufc_tapology"],
    #     shell=True,
    # )

    # Data = pd.read_csv("FightPredixAPP/Data/Data_jointes_ufc_tapology.csv")

    # logger.info("Lancement du scraping sur les combats")
    # combats = Dataframe_combats(main_driver)

    main_driver.quit()

    # logger.info("Scraping des données sur les arbitres sur UFC_fans")
    # subprocess.run(
    #     ["python", "-m", "FightPredix_scraping.scraping.lib_arbitre"], shell=True
    # )

    # logger.info("Construction des données finales")
    combats = _constructeur(Data, combats)

    # combats.to_csv("FightPredixAPP/Data/Data_final_combats.csv", index=False)

    # logger.info("Suppression des fichiers temporaires")
    # for file_path in [
    #     "FightPredixAPP/Data/Data_ufc_fighters.csv",
    #     "FightPredixAPP/Data/Data_jointes_ufc_tapology.csv",
    #     "FightPredixAPP/Data/data_tapology.csv",
    #     "FightPredixAPP/Data/clean_tapology.csv",
    # ]:
    #     if os.path.exists(file_path):
    #         os.remove(file_path)
    #         print(f"Le fichier {file_path} a été supprimé avec succès.")
    #     else:
    #         print(f"Le fichier {file_path} n'existe pas.")


if __name__ == "__main__":
    main()
