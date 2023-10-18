import requests
from bs4 import BeautifulSoup
import csv
import re
import os
import time

#convertit le rating d'un str en toutes lettres à un int
def rating_to_int(rating):
    rating_map = {
        "Zero": 0,
        "One": 1,
        "Two": 2,
        "Three": 3,
        "Four": 4,
        "Five": 5}
    return rating_map.get(rating, rating)
# extrait les informations de tous les livre d'une catégorie depuis la liste de leurs urls :
# Les infos extraites sont les suivantes
# - product_page_url
# - universal_ product_code (upc)
# - title
# - price_including_tax
# - price_excluding_tax
# - number_available
# - product_description
# - category
# - review_rating
# - image_url
# Puis les stocke dans une liste qui est retournée

def scrap_from_url(urls,name):
    result = [] #initialisation de la liste qui sera retournée en fin de fonction, contient une liste par livre de la catégorie
    for url in urls:
        data = [] #initialisation d'une liste contenant les infos pour 1 livre
        try: #gestion des erreurs dans la requete
            reponse = requests.get(url) #la variable reponse stocke la réponse à la request sur l'url renseignée
        except requests.exceptions.RequestException as e: #affiche l'erreur renvoyée
            print(e)        
        page = reponse.content #extrait le corps de la réposne via .content et le stocke dans page

        #parse le HTML en objet BeautifulSoup pour exploiter les données contenues
        soup = BeautifulSoup(page, "html.parser")

        #récupération de l'url
        product_page_url = url
        data.append(product_page_url) #ajout à la liste

        universal_product_code = soup.find("th", string="UPC") #trouve la balise 'th' contenant le texte 'UPC'
        universal_product_code = universal_product_code.find_next("td").string.strip() #isole le str contenu après la balise 'td' et la strip pour retirer les potentiels espaces avant/après
        data.append(universal_product_code) #ajoute la valeur à la liste data

        title = soup.find("h1").text.strip() #récupère le contenu de la balise h1 dans laquelle est stocké le titre
        data.append(title) #ajoute la valeur à la liste data

        #même principe que pour l'UPC
        price_including_tax = soup.find("th", string="Price (incl. tax)")
        price_including_tax = price_including_tax.find_next("td").string.strip()
        data.append(price_including_tax)

        #même principe que pour l'UPC
        price_excluding_tax = soup.find("th", string="Price (excl. tax)")
        price_excluding_tax = price_excluding_tax.find_next("td").string.strip()
        data.append(price_excluding_tax)

        #même principe que pour l'UPC
        number_available = soup.find("th", string="Availability")
        number_available = number_available.find_next("td").string.strip()
        number_available = re.search(r'\d+', number_available).group() #utilisation d'une regex pour extraire seulement la valeur du stock (initialement sous la forme "In stock (n available)")
        data.append(number_available)
        
        product_description = soup.find("meta", attrs={"name": "description"}) #cherche la balise meta avec un nom = description
        product_description = product_description["content"].strip() # Accede à "content" de la balise <meta> pour obtenir le contenu de la description
        data.append(product_description)

        category = soup.find("a", href=re.compile(r'/category/books/([\w-]+)/index.html')).string.strip() #utilisation d'une regex pour récupérer la valeur de la catégorie dans le href
        data.append(category) #ajoute la valeur à la liste data

        review_rating = soup.find("p", class_=re.compile(r'star-rating\s+(\w+)')) #idem ici avec une regex on récupère la partie située dans la balise 'p' avec 'star-rating'
        review_rating = re.search(r'\b(\w+)\b', review_rating["class"][1]).group(1) #extrait uniquement le chiffre en toutes lettres
        review_rating = review_rating.strip() #isole le str des potentiels espaces avant/après
        review_rating = rating_to_int(review_rating) #converti le str en int
        data.append(review_rating)
        
        image_url = soup.find("img")["src"] #trouve la balise <img> et accéder à l'attribut "src" pour obtenir l'URL de l'image
        image_url = image_url.replace("../","") #on retire les ../../ au début du lien
        image_url = "http://books.toscrape.com/" + image_url #on ajoute l'adresse du site pour avoir l'url complete de l'image
        data.append(image_url)

        #télécharge l'image associée à partir de l'objet soup
        download_img(image_url,title,name)

        result.append(data) #ajoute cette liste à la liste qui sera retournée avec les resultats
    return result

def clean_name(name):
    cleaned_name = re.sub(r'[<>:"/\\|?*]', '-', name) #utilisation d'une regex pour retirer tous les caracteres interdits dans un nom de fichier et les remplacer par "-"
    return cleaned_name #retourne le nom corrigé

#ecrit les données dans un fichier csv à partir des données et du nom désiré du fichier
def write_to_csv(datas,name):
    #création des headers
    headers = ["product_page_url","universal_product_code", "title", "price_including_tax", "price_excluding_tax",
               "number_available", "product_description", "category", "review_rating", "image_url"]
    
    file_path = os.path.join("scrap",name, f"{name}.csv") #initalisation de la variable contenant le chemin du fichier (nb : le dossier scrap est déjà créé dans la fonction download_img)

    with open(file_path, "w", newline='', encoding="utf-8") as file: #ecriture dans un csv parametre 'w' pour signifier la lecture, newline = '' pour ne pas avoir de saut de ligne en trop, encoding pour éviter les erreurs d'encodage
        writer = csv.writer(file, delimiter= ";") #initialiser l'objet writer avec le séparateur ;
        writer.writerow(headers) #ecrit les headers à la première ligne du fichier
        n = 0 #initialise un compteur

        for data in datas: #parcourt les données à ecrire
            writer.writerow(data)
            n += 1 #incrémente le compteur
            print(f"{data[2]} {n}/{len(datas)} catégorie {data[7]}") #affiche l'avancement de l'ecriture du csv (où data[2] est le titre et data[7] la catégorie)

#sert à récupérer toutes les url d'une seule catégorie
def get_all_url_from_section(url_section):  
    urls = [] #initialisation de la liste servant à stocker nos urls
    data = [] #initialisation de la liste qui sera retournée en fin de fontion contenant toutes les urls
    url_section_temp = url_section.split("index")[0] 
    while True: #cette boucle sert à gérer le cas où il y a plusieurs pages dans une seul catégorie
        #parsing de l'url donnée
        try: #gestion des erreurs dans la requete
            reponse = requests.get(url_section)
        except requests.exceptions.RequestException as e: #affiche l'erreur renvoyée
            print(e)
        page = reponse.content
        soup = BeautifulSoup(page, "html.parser")
        
        next_page = None #intialise la variable next_page en None
        urls.append(url_section) #ajoute l'url de la page n de la section à la liste

        try: # essaye d'acceder à l'url de la page suivante
            next_page = soup.find("li", class_="next").find("a")
        except: # si pas de next page on break la boucle while
            break

        if next_page is not None: #si il y a une autre page, on rentre dans cette boucle
            url_section = next_page["href"] #extrait la valeur de href pour récupérer la partie de l'url qui nous interesse
            url_section = url_section_temp + url_section #y ajoute le début de l'url du site car le href est sous la forme "page-n.html"

    for url in urls: #pacourt les urls de toutes les pages precedemment récupérées
        #parsing de la page via son url
        try: #gestion des erreurs dans la requete
            reponse = requests.get(url)
        except requests.exceptions.RequestException as e: #affiche l'erreur renvoyée
            print(e)
        page = reponse.content
        soup = BeautifulSoup(page, "html.parser")

        h3_tags = soup.find_all("h3") #récupère les balises h3 contenant les urls des livres

        for h3_tag in h3_tags: #parcourt les balises h3 précédemment récupérées
            link_tag = h3_tag.a #isole la valeur de la balise a
            href_value = link_tag["href"] #récupère la valeur du href
            href_value = href_value.replace("../","") #retire les ../../ en début d'url
            href_value = ("http://books.toscrape.com/catalogue/" + href_value) #complete l'url pour qu'elle soit valide
            data.append(href_value) #ajoute l'url récupée dans la liste data

    return data
#sert à télécharger l'image depuis son url sous le nom du livre associé et dans un dossier avec le nom de la catégorie associée
def download_img(img_url,name,category):
    if not os.path.exists("scrap"): #vérifie si le dossier scrap existe (dossier qui sert à stocker toutes les données)
        os.makedirs("scrap") #créé le dossier si il n'existe pas déjà

    if not os.path.exists(f"scrap\{category}"): #vérifie si le dossier avec le nom de la catégorie existe dans le dossier scrap créé plus haut
        os.makedirs(f"scrap\{category}") #créé le dossier si il n'existe pas déjà

    name = clean_name(name) #nettoye le nom du fichier en retirant les carcteres interdits
    file_path = os.path.join("scrap",category, f"{name}.jpg") #initialise la variable contenant le chemin où enregistrer l'image et son nom

    with open(file_path, "wb") as file: #ouvre un fichier avec le chemin créé ci dessus avec le parametre w pour ecrire et b pour ouvrir en mode binaire (car données non textuelles)
        try: #gestion des erreurs dans la requete
            response = requests.get(img_url) #lance une request avec l'url de l'image
        except requests.exceptions.RequestException as e: #affiche l'erreur renvoyée
            print(e)       

        if not response.ok: #gestion des erreurs
           print(response) #affiche l'erreur retournée si la request échoue

        for block in response.iter_content(1024): #itere dans les données renvoyées par l'image, 1024 est le nb
            if not block:                         #d'octet à télécharger à chaque itération
                break

            file.write(block) #ecrit le fichier dans le path spécifié

#sert à récupérer les urls de chacune des catégories du site
def get_all_section(url):
    try: #gestion des erreurs dans la requete
        reponse = requests.get(url) #récupère la réponse de la request sur une url données
    except requests.exceptions.RequestException as e: #affiche l'erreur renvoyée
        print(e)
    page = reponse.content #créé une variable avec le contenu de cette réponse
    soup = BeautifulSoup(page, "html.parser") #parse la variable via le parser de BeautifulSoup (gagner en lisibilité)
    data = [] #initialisation de la liste qui stocke les urls
    all_cat = soup.find("ul", class_="nav nav-list") #isole la classe nav nav-list de la balise ul
    hrefs = all_cat.find_all("a", href=True) #puis extrait la valeur de chaque balise "a" uniquement si la valeur de href n'est pas nulle

    for href in hrefs: #parcourt les valeurs des hrefs extraits au dessus
        href = href["href"] #extrait la valeur seule de href
        url = ("http://books.toscrape.com/" + href) #ajoute la partie manquante de l'url (href est sous la forme ../category_n°category/index.html)
        data.append(url) #ajoute l'url à la liste de données à retourner

    data.remove("http://books.toscrape.com/catalogue/category/books_1/index.html") #retire la première URL qui contient tous les livres sans classement
    return(data)

def main():
    start_time = time.time() #initialisation de la variable permettant de calculer le temps mis à executer le script
    total_scrapped = 0 #initialisation du compteur de livre total scrappé
    n = 0 #compteur
    url_home = "http://books.toscrape.com/index.html" #url de l'accueil du site
    url_category = get_all_section(url_home) #récupère les urls de toutes les sections depuis l'adresse d'accueil du site (url_home)

    for url in url_category: #parcourt les urls de chaque catégorie
        match = re.search(r'\/([^\/]+)_\d+\/', url) #utilisation d'une regex pour isoler le nom de la catégorie dans l'url
        name = match.group(1)
        url_section = get_all_url_from_section(url) #récupère les urls de chaque livre dans une section et les stocke dans une liste (url_section)
        scrapped_data = scrap_from_url(url_section,name) #scrap les données pour chaque url récupérée ci dessus
        write_to_csv(scrapped_data,name) #ecrit les données dans un csv
        n += 1 #incrémente le compteur
        total_scrapped += len(url_section) #incrémente le total de livre scrappé
        print (f"catégorie {n} sur {len(url_category)} {name} terminée avec {len(url_section)} livres scrappé(s)") #résumé le nb de livres scrappés dans la ctégorie en cours

    end_time = time.time() #temps une fois le script terminé
    elapsed_time = end_time - start_time #calcul du temps d'execution total
    print(f" {total_scrapped} livres scrappés en {int(elapsed_time // 60)} minutes et {int(elapsed_time % 60)} secondes") #affichage du temps d'execution total

if __name__ == "__main__":
    main()