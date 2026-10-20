import { FACILITY_TAB_SPECS } from '../config/facilityTabsConfig';
import { partitionGoogleBusinessLabels } from './googlePlacesDisplay';
import { isLikelyEnglishFacilityText, localizeFacilityLabel } from './facilityLabelsId';

export function toReadableLabel(key, labels = {}) {
  if (!key) return '';
  const snake = String(key).trim().toLowerCase().replace(/\s+/g, '_').replace(/-/g, '_');
  if (labels[snake]) return labels[snake];
  if (labels[key]) return labels[key];
  return localizeFacilityLabel(key, labels);
}

export function uniqueStrings(list) {
  const seen = new Set();
  const out = [];
  (list || []).forEach((item) => {
    const key = String(item || '').trim();
    if (!key || seen.has(key)) return;
    seen.add(key);
    out.push(key);
  });
  return out;
}

function orderedTrueKeys(sourceObj, preferredOrder = []) {
  if (!sourceObj || typeof sourceObj !== 'object') return [];
  const keys = Object.entries(sourceObj)
    .filter(([, value]) => value === true)
    .map(([key]) => key);

  const orderIndex = (key) => {
    const i = preferredOrder.indexOf(key);
    return i === -1 ? preferredOrder.length : i;
  };

  return keys.sort((a, b) => orderIndex(a) - orderIndex(b) || a.localeCompare(b));
}

function itemsFromBooleanDict(block, labelMap, keyOrder) {
  if (!block || typeof block !== 'object' || Array.isArray(block)) return [];
  return orderedTrueKeys(block, keyOrder || []).map((key) => toReadableLabel(key, labelMap || {}));
}

function itemsFromAccessibilityBlock(block) {
  if (!block || typeof block !== 'object') return [];
  const items = [];
  if (block.wheelchair_accessible_entrance === true) {
    items.push('Akses kursi roda');
  } else if (block.wheelchair_accessible_entrance === false) {
    items.push('Tanpa akses kursi roda');
  }
  Object.entries(block).forEach(([key, value]) => {
    if (key === 'wheelchair_accessible_entrance') return;
    if (value === true) items.push(toReadableLabel(key));
    else if (value === false) items.push(`Tanpa ${toReadableLabel(key).toLowerCase()}`);
  });
  return items;
}

function itemsFromCrowdLike(block, labelMap) {
  if (Array.isArray(block)) {
    return block
      .map((entry) => toReadableLabel(String(entry || ''), labelMap || {}))
      .filter(Boolean);
  }
  return itemsFromBooleanDict(block, labelMap);
}

function itemsForSpec(spec, facilities, extras) {
  const f = facilities || {};
  const labelMap = spec.labelMap || {};
  const keyOrder = spec.keyOrder || [];

  switch (spec.id) {
    case 'accessibility':
      return uniqueStrings([
        ...itemsFromAccessibilityBlock(f.accessibility),
        ...(extras.googleAccessibility || []),
      ]);
    case 'highlights':
      return uniqueStrings([
        ...itemsFromBooleanDict(f.highlights, labelMap, keyOrder),
        ...(extras.googleHighlights || []),
      ]);
    case 'amenities': {
      const atmosphereItems = (Array.isArray(f.atmosphere) ? f.atmosphere : [])
        .map((item) => String(item || '').trim())
        .filter((item) => item && !isLikelyEnglishFacilityText(item))
        .map((item) => toReadableLabel(item))
        .filter(Boolean);
      return uniqueStrings([
        ...itemsFromBooleanDict(f.amenities, labelMap, keyOrder),
        ...atmosphereItems,
        ...(extras.googleLainnya || []),
      ]);
    }
    case 'crowd':
      return uniqueStrings([
        ...itemsFromCrowdLike(f.crowd, labelMap),
        ...itemsFromBooleanDict(f.children, labelMap),
      ]);
    default:
      if (spec.facilityKey) {
        return itemsFromBooleanDict(f[spec.facilityKey], labelMap, keyOrder);
      }
      if (spec.facilityKeys) {
        return uniqueStrings(
          spec.facilityKeys.flatMap((key) => itemsFromCrowdLike(f[key], labelMap)),
        );
      }
      return [];
  }
}

/**
 * Bangun item per tab id dari facilities JSON + atribut Google (snapshot).
 */
export function buildFacilityTabItems(facilities, googleSnapshot) {
  const partitioned = partitionGoogleBusinessLabels(googleSnapshot?.business_attributes);
  const extras = {
    googleAccessibility: partitioned.accessibility,
    googleHighlights: partitioned.highlights,
    googleLainnya: partitioned.lainnya,
  };

  const out = {};
  FACILITY_TAB_SPECS.forEach((spec) => {
    const labelMap = spec.labelMap || {};
    out[spec.id] = itemsForSpec(spec, facilities, extras)
      .map((item) => localizeFacilityLabel(item, labelMap))
      .filter((item) => item && !isLikelyEnglishFacilityText(item));
  });
  return out;
}
