// Matcher do getByText para texto que o React parte em vários nós (ícone + nome de magia):
// acha o elemento mais interno cujo texto exibido inteiro é `text`.
import { plainSpellText } from "../lib/spellText.js";

export const byPlainText = (text) => (_content, element) =>
  element.textContent === text &&
  ![...element.children].some((child) => child.textContent === text);

export const byMarkedText = (marked) => byPlainText(plainSpellText(marked));
