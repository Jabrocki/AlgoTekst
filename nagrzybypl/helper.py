import re
from pathlib import Path

def znajdz_krotkie_pliki(folder="atlas_grzybow", max_dlugosc=220):
    sciezka_folderu = Path(folder)
    
    if not sciezka_folderu.exists() or not sciezka_folderu.is_dir():
        print(f"Błąd: Folder '{folder}' nie istnieje.")
        return

    znalezione_pliki = []
    usune=[]    
    for plik in sciezka_folderu.iterdir():
        if plik.is_file() and plik.suffix.lower() == ".md":
            try:
                with plik.open("r", encoding="utf-8") as f:
                    zawartosc = f.read()
                    if len(zawartosc) < max_dlugosc:
                        znalezione_pliki.append(plik.name)
                        usune.append(plik)
            except Exception as e:
                print(f"Błąd przy odczycie pliku '{plik.name}': {e}")


    for plik in usune:
        try:
            plik.unlink()
        except Exception as e:
            print(f"Błąd przy usuwaniu pliku '{plik}': {e}")

    print("=" * 50)
    print(f"Znaleziono plików .md krótszych niż {max_dlugosc} znaków: {len(znalezione_pliki)}")
    for nazwa in znalezione_pliki:
        print(f" - {nazwa}")
    print("=" * 50)


def znajdz_pliki_z_dziwnymi_znakami(folder="atlas_grzybow"):
    sciezka_folderu = Path(folder)
    
    if not sciezka_folderu.exists() or not sciezka_folderu.is_dir():
        print(f"Błąd: Folder '{folder}' nie istnieje.")
        return

    znalezione_pliki = []
    
    wzorzec = re.compile(r'[^a-z_]')

    for plik in sciezka_folderu.iterdir():
        if plik.is_file():
            #if wzorzec.search(plik.stem):
                #znalezione_pliki.append(plik.name)
            if 'var.' in plik.name:
                znalezione_pliki.append(plik.name)
                plik.rename(plik.parent / plik.name.replace('var.', 'varietas'))
            elif 'spp.' in plik.name:
                znalezione_pliki.append(plik.name)
                plik.rename(plik.parent / plik.name.replace('spp.', 'species'))
            elif 'sp.' in plik.name:
                znalezione_pliki.append(plik.name)
                plik.rename(plik.parent / plik.name.replace('sp.', 'species'))
            elif 'subsp.' in plik.name:
                znalezione_pliki.append(plik.name)
                plik.rename(plik.parent / plik.name.replace('subsp.', 'subspecies'))
            elif 'f.' in plik.name:
                znalezione_pliki.append(plik.name)
                plik.rename(plik.parent / plik.name.replace('f.', 'forma'))

    print("=" * 50)
    print(f"Znaleziono plików z niedozwolonymi znakami w nazwie: {len(znalezione_pliki)}")
    for nazwa in znalezione_pliki:
        print(f" - {nazwa}")
    print("=" * 50)




if __name__ == "__main__":
    
    znajdz_krotkie_pliki()
    print("\n")
    znajdz_pliki_z_dziwnymi_znakami()
