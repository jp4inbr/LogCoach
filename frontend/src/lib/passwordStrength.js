// Força da senha no cadastro: só um termômetro para o cliente ter noção. Não bloqueia nada;
// a única exigência continua sendo o mínimo de 8 caracteres do backend.

export const MIN_PASSWORD = 8;

// Palavras que aparecem em listas de senhas vazadas ou que são óbvias neste site.
const COMMON_WORDS = [
  "senha",
  "password",
  "qwerty",
  "asdf",
  "abc",
  "admin",
  "teste",
  "logcoach",
  "warcraft",
  "wow",
  "mago",
  "brasil",
];

export const STRENGTH_LEVELS = ["Fraca", "Razoável", "Boa", "Forte"];

function classes(password) {
  return [/[a-z]/, /[A-Z]/, /[0-9]/, /[^A-Za-z0-9]/].filter((re) => re.test(password)).length;
}

// "aaaaaaaa", "12345678", "abcdefgh", "87654321": um caractere só ou sequência.
function isTrivial(password) {
  if (new Set(password).size <= 2) return true;
  const codes = [...password.toLowerCase()].map((c) => c.codePointAt(0));
  const steps = new Set(codes.slice(1).map((code, i) => code - codes[i]));
  return steps.size === 1 && [1, -1].includes([...steps][0]);
}

/**
 * Nível de 0 (Fraca) a 3 (Forte), com o nome e uma dica do que melhorar.
 * Vazio: null (a tela não mostra o medidor).
 */
export function passwordStrength(password) {
  if (!password) return null;
  const lower = password.toLowerCase();
  const kinds = classes(password);
  let points =
    (password.length >= MIN_PASSWORD) +
    (password.length >= 12) +
    (password.length >= 16) +
    (kinds >= 2) +
    (kinds >= 3);

  const hasCommon = COMMON_WORDS.some((word) => lower.includes(word));
  const bare = lower.replace(/[^a-z]/g, "");
  if (isTrivial(password) || COMMON_WORDS.includes(bare)) points = Math.min(points, 1);
  else if (hasCommon) points -= 1;
  if (password.length < MIN_PASSWORD) points = 0;

  const level = points <= 1 ? 0 : points === 2 ? 1 : points === 3 ? 2 : 3;

  let tip = null;
  if (password.length < MIN_PASSWORD) tip = `Use pelo menos ${MIN_PASSWORD} caracteres.`;
  else if (isTrivial(password) || hasCommon)
    tip = "Evite palavras comuns (como “senha”) e sequências (como “1234”).";
  else if (password.length < 12) tip = "Com 12 caracteres ou mais ela fica bem mais forte.";
  else if (kinds < 3) tip = "Misture letras maiúsculas, números ou símbolos.";

  return { level, label: STRENGTH_LEVELS[level], tip };
}
