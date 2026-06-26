type RadixColor = "gray" | "blue" | "green" | "amber" | "red";

export const ORDER_STATUS_LABELS: Record<string, string> = {
  received: "Reçue",
  waiting_intake: "En attente formulaire",
  processing: "En traitement",
  delivered: "Livrée",
  failed: "Échec",
  cancelled: "Annulée",
};

export function orderStatusColor(status: string): RadixColor {
  const map: Record<string, RadixColor> = {
    received: "gray",
    waiting_intake: "amber",
    processing: "blue",
    delivered: "green",
    failed: "red",
    cancelled: "gray",
  };
  return map[status] ?? "gray";
}
