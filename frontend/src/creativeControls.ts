export const levelIndex = (value: number) => value < 34 ? 0 : value < 67 ? 1 : 2
export const levelValue = (value: number) => [0, 50, 85][levelIndex(value)]
export const poseStrength = (value: number) => Math.round((0.4 + 0.6 * value / 100) * 100) / 100
export const controlCopy = (fr: boolean) => fr ? {
  fidelity: 'Fidélité aux références', freedom: 'Liberté créative', pose: 'Respect du mouvement',
  fidelityLevels: ['Souple', 'Équilibrée', 'Stricte'], freedomLevels: ['Fidèle', 'Équilibrée', 'Audacieuse'],
  fidelityHint: 'Fidélité au cadrage et au traitement des références. Identité et produit restent préservés.',
  freedomHint: 'Liberté de mise en scène dans les limites du brief ; ne change pas le genre musical ni le nombre de plans demandé.',
  poseHint: 'Force du guidage de pose en Remix, de 0,40 à 1,00. Le minimum conserve un guidage ; ce n’est pas un taux de fidélité.',
  noRefs: 'Ajoute une référence visuelle pour régler sa fidélité.',
  scope: 'Ces réglages s’appliquent à une nouvelle génération. Régénérer un plan conserve les réglages de son projet.',
} : {
  fidelity: 'Reference fidelity', freedom: 'Creative freedom', pose: 'Motion guidance',
  fidelityLevels: ['Flexible', 'Balanced', 'Strict'], freedomLevels: ['Faithful', 'Balanced', 'Bold'],
  fidelityHint: 'Fidelity to reference framing and treatment. Subject identity and product design remain preserved.',
  freedomHint: 'Staging freedom within the brief; does not change the requested music genre or shot count.',
  poseHint: 'Remix pose-guidance strength, from 0.40 to 1.00. The minimum retains guidance; this is not a fidelity score.',
  noRefs: 'Add a visual reference to adjust its fidelity.',
  scope: 'These settings apply to a new generation. Regenerating a shot keeps its project settings.',
}
