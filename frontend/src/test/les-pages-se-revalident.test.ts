/** Les pages HTML se revalident à chaque visite (`Cache-Control: no-cache`).
 *
 * Le 25/11/2026, après une mise en ligne, un navigateur montrait encore
 * l'ancienne page Professionnels : sans en-tête de cache, il gardait la page
 * selon une heuristique. Mesuré ensuite dans un nginx réel : `/partenaires`
 * et `/` rendent `no-cache`, `/assets/…` garde son année de cache.
 *
 * Ce test lit la configuration : il ne remplace pas `nginx -t`, il empêche
 * qu'on retire la règle sans le voir.
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const CONF = readFileSync(join(__dirname, "..", "..", "nginx.conf"), "utf-8");

describe("les pages se revalident", () => {
  it("le HTML sans en-tête de cache reçoit « no-cache », et seulement lui", () => {
    const bloc = CONF.match(/map "\$sent_http_content_type\|\$sent_http_cache_control" \$cache_des_pages \{[^}]*\}/);
    expect(bloc).not.toBeNull();
    expect(bloc?.[0]).toContain('default "";');
    expect(bloc?.[0]).toContain('"~^text/html[^|]*\\|$" "no-cache";');
  });

  it("le serveur pose l'en-tête, et les fichiers de /assets/ gardent leur cache long", () => {
    expect(CONF).toContain("add_header Cache-Control $cache_des_pages;");
    expect(CONF).toMatch(/location \^~ \/assets\/ \{\s*add_header Cache-Control "public, max-age=31536000, immutable";/);
  });
});
