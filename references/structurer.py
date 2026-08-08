#!/usr/bin/env python3
"""Structure le JSON extrait en sections nommees, en-tetes et pieds inclus."""
import json, re, sys, zipfile

def header_footer(docx):
    out = {}
    with zipfile.ZipFile(docx) as z:
        for part, key in (('word/header1.xml', 'en_tete'), ('word/footer1.xml', 'pied_de_page')):
            try:
                s = z.read(part).decode('utf-8')
                out[key] = ' '.join(re.findall(r'<w:t[^>]*>([^<]*)</w:t>', s)).strip()
            except KeyError:
                out[key] = ''
    return out

def split_front(blocs):
    """Decoupe l'avant-document en page de garde / synthese / sommaire / mode d'emploi."""
    sections = {'page_de_garde': [], 'synthese_executive': [], 'sommaire': [], 'mode_emploi': []}
    cible = 'page_de_garde'
    for b in blocs:
        txt = b.get('texte', '') if b['type'] == 'paragraphe' else ''
        if txt == 'Synthèse exécutive':
            cible = 'synthese_executive'; continue
        if txt == 'Sommaire':
            cible = 'sommaire'; continue
        if txt.startswith('Mode d’emploi') or txt.startswith("Mode d'emploi"):
            cible = 'mode_emploi'; continue
        if b['type'] == 'saut_de_page':
            continue
        sections[cible].append(b)
    return sections

def split_back(dernier_chapitre):
    """Detache la quatrieme de couverture (apres le dernier graphique)."""
    blocs = dernier_chapitre['blocs']
    idx = max(i for i, b in enumerate(blocs) if b['type'] == 'graphique')
    dernier_chapitre['blocs'], dos = blocs[:idx], blocs[idx:]
    return dos

def main(json_in, docx, json_out):
    d = json.load(open(json_in, encoding='utf-8'))
    chapitres = d['chapitres']
    # fusionner preambule (logo seul) + section sans titre = avant-document
    avant = []
    while chapitres and not chapitres[0]['numero'].startswith('CHAPITRE'):
        avant.extend(chapitres.pop(0)['blocs'])
    front = split_front(avant)
    dos = split_back(chapitres[-1])

    for c in chapitres:
        c['statistiques'] = {
            'signes': sum(b.get('signes', 0) for b in c['blocs']),
            'paragraphes': sum(1 for b in c['blocs'] if b['type'] == 'paragraphe'),
            'tableaux': sum(1 for b in c['blocs'] if b['type'] == 'tableau'),
            'graphiques': sum(1 for b in c['blocs'] if b['type'] == 'graphique'),
            'encadres': sum(1 for b in c['blocs'] if b['type'] == 'encadre'),
            'grilles_kpi': sum(1 for b in c['blocs'] if b['type'] == 'grille_kpi'),
        }

    out = {
        'type_document': 'etude_de_marche',
        'source': d['source'],
        'gabarit': header_footer(docx),
        'page_de_garde': front['page_de_garde'],
        'synthese_executive': front['synthese_executive'],
        'sommaire': front['sommaire'],
        'mode_emploi': front['mode_emploi'],
        'nb_chapitres': len(chapitres),
        'chapitres': chapitres,
        'quatrieme_de_couverture': dos,
        'totaux': d['totaux'],
    }
    json.dump(out, open(json_out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(json_out, ':')
    for k in ('page_de_garde', 'synthese_executive', 'sommaire', 'mode_emploi', 'quatrieme_de_couverture'):
        print('  %-24s %d blocs' % (k, len(out[k])))
    print('  chapitres                %d' % len(chapitres))

if __name__ == '__main__':
    main(sys.argv[1], sys.argv[2], sys.argv[3])
