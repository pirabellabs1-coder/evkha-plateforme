import { useState } from "react";
import { Card, Flex, Box, Text, Heading, TextField, Button } from "@radix-ui/themes";
import { setToken } from "../auth";

/** Où atterrit un administrateur qui vient de présenter son jeton.
 *
 * Cette page redirigeait vers `/`. C'était juste au temps où `/` servait le
 * tableau de bord ; depuis que la racine rend la page partenaires — publique —,
 * coller un jeton d'administration menait sur le site vitrine. Le jeton était
 * pourtant bien enregistré : rien n'échouait, on n'arrivait simplement jamais.
 *
 * La destination est nommée ici, à côté du geste qui l'emprunte, pour qu'un
 * futur changement de racine ne puisse plus la déplacer en silence.
 */
export const APRES_CONNEXION = "/admin";

export function Login() {
  const [value, setValue] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const trimmed = value.trim();
    if (!trimmed) {
      setError("Le token ne peut pas être vide.");
      return;
    }
    setToken(trimmed);
    // Rechargement complet et non navigation interne : la garde de route lit
    // le jeton au chargement, et l'application doit repartir avec.
    window.location.href = APRES_CONNEXION;
  }

  return (
    <Flex align="center" justify="center" style={{ minHeight: "100vh", background: "var(--gray-2)" }}>
      <Card size="4" style={{ width: "100%", maxWidth: 400 }}>
        <Flex align="center" gap="3" mb="5">
          <Text style={{ fontSize: 28, color: "var(--accent-9)" }}>⬡</Text>
          <Box>
            <Heading size="4" as="h1">EVKHA</Heading>
            <Text size="1" color="gray">Dashboard · accès administrateur</Text>
          </Box>
        </Flex>

        <form onSubmit={handleSubmit}>
          <Box mb="4">
            <Text as="label" htmlFor="token" size="1" weight="bold"
              style={{ display: "block", textTransform: "uppercase", letterSpacing: "0.05em", marginBottom: 6 }}>
              Token d'accès
            </Text>
            <TextField.Root
              id="token"
              type="password"
              placeholder="Coller le token ici…"
              value={value}
              onChange={(e) => { setValue(e.target.value); setError(""); }}
              autoFocus
              size="3"
            />
            {error && (
              <Text size="1" color="red" as="p" mt="1">{error}</Text>
            )}
          </Box>

          <Button type="submit" size="3" style={{ width: "100%" }} disabled={!value.trim()}>
            Accéder au dashboard
          </Button>
        </form>

        <Text size="1" color="gray" as="p" mt="4" align="center">
          Le token se trouve dans <Text as="span" style={{ fontFamily: "var(--font-mono)", background: "var(--gray-3)", padding: "1px 5px", borderRadius: "var(--radius-1)" }}>EVKHA_DASHBOARD_TOKEN</Text> (Coolify env vars).
        </Text>
      </Card>
    </Flex>
  );
}
