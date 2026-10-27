"""Kutipan, modal, dan metadata gate untuk bukti rekomendasi."""
from __future__ import annotations

from recommendation import helpers as _h
from recommendation.helpers import *  # noqa: F403
from recommendation.helpers import _split_preference_pills


def _bind_helpers_private_api() -> None:
    """Star-import tidak mengekspor `_MIN_QUOTE_CHARS`, `_normalize_whitespace`, dll."""
    g = globals()
    for name, val in vars(_h).items():
        if name.startswith('__'):
            continue
        if name.startswith('_') and name not in g:
            g[name] = val


_bind_helpers_private_api()
del _bind_helpers_private_api

def _facilities_item_matches_intent(item_label, intent_blob_lower):
    if not item_label or not intent_blob_lower:
        return False
    blob = intent_blob_lower
    label = str(item_label).strip().lower()
    label_norm = re.sub(r'[^\w\s]', ' ', label)
    for token in label_norm.split():
        tok = token.strip()
        if len(tok) >= 3 and tok in blob:
            return True
        if len(tok) <= 2 and tok and re.search(r'\b' + re.escape(tok) + r'\b', blob):
            return True
    compact = re.sub(r'\s+', ' ', label_norm).strip()
    if len(compact) >= 5 and compact in blob:
        return True
    return False
def _facilities_tab_display_for_intent(facilities_tab, intent_blob_lower):
    """
    Jika ada label fasilitas yang overlap dengan intent user, kembalikan subset itu;
    jika tidak, kembalikan penuh (tetap sebagai konteks profil tempat).
    """
    full = facilities_tab or {}

    def _filt(items):
        if not isinstance(items, list):
            return []
        return [x for x in items if _facilities_item_matches_intent(x, intent_blob_lower)]

    if not (intent_blob_lower or '').strip():
        return full, False

    rel = {
        'popular_for': _filt(full.get('popular_for')),
        'highlights': _filt(full.get('highlights')),
        'atmosphere': _filt(full.get('atmosphere')),
    }
    if any(rel.get(k) for k in ('popular_for', 'highlights', 'atmosphere')):
        return rel, True
    return full, False
def _build_facilities_evidence_summary(display_tab, intent_aligned):
    """Kalimat bukti berbasis tab fasilitas (popular_for, atmosphere, highlights)."""
    pop = list(display_tab.get('popular_for') or [])
    atm = list(display_tab.get('atmosphere') or [])
    hi = list(display_tab.get('highlights') or [])
    if not (pop or atm or hi):
        return ''
    parts = []
    if pop:
        parts.append(f"terkenal dengan {', '.join(pop[:6])}")
    if atm:
        parts.append(f"memiliki suasana {', '.join(atm[:6])}")
    if hi:
        parts.append(f"memiliki keunggulan {', '.join(hi[:6])}")
    if len(parts) == 1:
        body = parts[0]
    elif len(parts) == 2:
        body = f"{parts[0]} dan {parts[1]}"
    else:
        body = f"{parts[0]}, {parts[1]}, dan {parts[2]}"
    text = f"Berdasarkan tab fasilitas, coffee shop ini {body}."
    if intent_aligned:
        text += " Ini selaras dengan preferensi yang Anda masukkan."
    return text
def _build_metadata_support_items(evidence, *, facilities_tab_intent=None, facilities_intent_aligned=None):
    """Info metadata yang cocok intent user; hanya untuk tampilan, bukan skoring."""
    ev = evidence or {}
    out = []
    seen = set()

    def push(kind, title, items, note):
        clean_items = [str(x).strip() for x in (items or []) if str(x or '').strip()]
        if not clean_items:
            return
        key = (kind, tuple(clean_items[:6]))
        if key in seen:
            return
        seen.add(key)
        out.append({
            'type': kind,
            'title': title,
            'items': clean_items[:6],
            'note': note,
            'source': 'metadata',
        })

    gate = ev.get('metadata_gate') or {}
    matched_labels = [
        str(x).strip()
        for x in (gate.get('matched_attribute_labels') or ev.get('matched_facility_labels') or [])
        if str(x or '').strip()
    ]
    if matched_labels:
        push(
            'profile_facility',
            'Profil fasilitas',
            matched_labels,
            'Klaim profil tempat yang cocok dengan fasilitas tambahan pilihan Anda.',
        )

    tab = facilities_tab_intent if facilities_tab_intent is not None else ev.get('facilities_tab_intent')
    aligned = (
        bool(facilities_intent_aligned)
        if facilities_intent_aligned is not None
        else bool(ev.get('facilities_intent_aligned'))
    )
    if aligned and isinstance(tab, dict):
        for key, title in (
            ('popular_for', 'Populer untuk'),
            ('highlights', 'Keunggulan'),
            ('atmosphere', 'Suasana'),
        ):
            values = tab.get(key) or []
            push(
                f'facility_tab_{key}',
                title,
                values,
                'Metadata fasilitas yang cocok dengan intent pencarian Anda.',
            )

    return out[:4]
def _quote_ui_extras(src):
    """Field opsional yang diwariskan ke JSON kutipan untuk UI."""
    if not isinstance(src, dict):
        return {}
    out = {}
    for k in ('review_id', 'rating_makanan', 'rating_layanan', 'rating_suasana'):
        if src.get(k) is not None:
            out[k] = src[k]
    if 'has_photos' in src:
        out['has_photos'] = bool(src['has_photos'])
    return out
def _quote_completeness_score(q):
    """Jumlah sinyal rating/foto yang terisi pada satu kutipan (untuk urutan sekunder)."""
    n = 0
    if q.get('rating') is not None and q.get('rating') != '':
        n += 1
    for k in ('rating_layanan', 'rating_suasana', 'rating_makanan'):
        if q.get(k) is not None and q.get(k) != '':
            n += 1
    if q.get('has_photos'):
        n += 1
    return n
def _quote_llm_verdict(quote_text):
    """
    Verdict LLM untuk satu kutipan bila kutipan itu sudah dinilai pada request ini.
    None berarti belum dinilai, sehingga pemanggil memakai heuristik lama.
    """
    verdicts = _clause_verdicts_var.get()
    if not verdicts:
        return None
    return verdicts.get(clause_quote_key(quote_text))
def _quote_has_unsuitability_phrase(quote_text):
    """True jika kutipan secara eksplisit menolak kecocokan (kurang/tidak disarankan)."""
    normalized = _normalize_keyword_phrase(quote_text)
    if not normalized:
        return False
    return any(phrase in normalized for phrase in _UNSUITABILITY_PHRASES)
def _quote_mentions_activity(quote_text, activity_pills, activity_tokens):
    text = str(quote_text or '')
    if not text.strip():
        return False
    if activity_tokens and text_matches_tokens(text, activity_tokens):
        return True
    for pill in activity_pills or []:
        for keyword in _expand_pill_to_keywords(pill):
            if _matches_keyword_phrase(text, keyword):
                return True
    return False
def _quote_rejects_activity(quote_text, activity_pills, activity_tokens, activity_matcher=None):
    """Kontradiksi: klausa yang sama menyebut aktivitas dan menolaknya."""
    return text_rejects_requested_activity(
        quote_text, activity_matcher, activity_tokens,
    )
def _quote_llm_label(quote_text):
    """Label sentimen LLM: supporting | caveat | irrelevant, atau None bila belum dinilai."""
    verdict = _quote_llm_verdict(quote_text)
    if not isinstance(verdict, dict):
        return None
    label = str(verdict.get('label') or '').strip().lower()
    if label in ('supporting', 'caveat', 'irrelevant'):
        return label
    return None
def _quote_destination(quote_text, default):
    """
    Bucket kutipan: supporting | caveat | None (buang).
    Frasa ekstrem (kurang/tidak disarankan) selalu caveat, termasuk jika LLM
    sempat menandai supporting. Tanpa itu, verdict LLM menang.
    """
    if _quote_has_unsuitability_phrase(quote_text):
        return 'caveat'
    label = _quote_llm_label(quote_text)
    if label is None:
        return default
    if label == 'irrelevant':
        return None
    return label
def _quote_marker_key(quote_text):
    return clause_quote_key(str(quote_text or '').strip())
def _attach_metadata_gate_to_evidence(
    evidence,
    score_detail=None,
    metadata_gate=None,
    reviews=None,
):
    """Salin prior/penalti metadata ke evidence + caveat jika ulasan menentang klaim."""
    ev = dict(evidence or {})
    gate = metadata_gate or (score_detail or {}).get('metadata_gate')
    if not isinstance(gate, dict) and isinstance(score_detail, dict):
        gate = {
            'claimed_pills': score_detail.get('metadata_claimed_pills') or [],
            'contradicted_pills': score_detail.get('metadata_contradicted_pills') or [],
            'matched_attribute_pills': score_detail.get('metadata_matched_attribute_pills') or [],
            'matched_attribute_labels': score_detail.get('metadata_matched_attribute_labels') or [],
            'prior': score_detail.get('metadata_prior') or 0.0,
            'contradiction': score_detail.get('metadata_contradiction') or 0.0,
            'quotes': [],
        }
    gate = gate or {}
    quotes = list(gate.get('quotes') or ev.get('metadata_contradiction_quotes') or [])
    claimed = list(gate.get('claimed_pills') or [])
    contradicted = list(gate.get('contradicted_pills') or [])
    matched_pills, matched_labels = _matched_facility_from_gate(
        gate,
        score_detail,
        reviews=reviews,
    )
    ev['metadata_gate'] = {
        'claimed_pills': claimed,
        'contradicted_pills': contradicted,
        'matched_attribute_pills': matched_pills,
        'matched_attribute_labels': matched_labels,
        'prior': gate.get('prior') or 0.0,
        'contradiction': gate.get('contradiction') or 0.0,
        'prior_boost': (score_detail or {}).get('metadata_prior_boost'),
        'penalty': (score_detail or {}).get('metadata_penalty'),
    }
    ev['matched_facility_pills'] = matched_pills
    ev['matched_facility_labels'] = matched_labels
    ev['metadata_contradiction_quotes'] = quotes
    ev['metadata_support'] = _build_metadata_support_items(ev)
    if contradicted:
        labels = [PILL_LABELS.get(p, p) for p in contradicted]
        ev['facilities_evidence_summary'] = (
            'Profil tempat menandai '
            + _join_indonesian_topics([str(label).lower() for label in labels])
            + ', tetapi ulasan pengunjung menentang klaim itu.'
        )
    elif matched_labels:
        note = (
            'Profil tempat menandai '
            + _join_indonesian_topics([str(label).lower() for label in matched_labels])
            + ' (klaim pendukung, bukan bukti utama).'
        )
        if not ev.get('facilities_evidence_summary'):
            ev['facilities_evidence_summary'] = note
    if quotes:
        ev['modal_caveat_quotes'] = _merge_caveat_quote_rows(
            quotes,
            ev.get('modal_caveat_quotes'),
            limit=2,
        )
    return ev
def _quote_is_caveat(quote_text, preference_keywords):
    """
    True bila kutipan tidak layak dipakai sebagai bukti kecocokan.

    Urutan:
      1. frasa ekstrem ("kurang/tidak disarankan") — selalu caveat
      2. verdict LLM per kutipan
      3. heuristik jendela token (fallback)
    """
    text = str(quote_text or '')
    if len(text.strip()) < _MIN_QUOTE_CHARS:
        return False
    if _quote_has_unsuitability_phrase(text):
        return True
    llm_label = _quote_llm_label(text)
    if llm_label is not None:
        return llm_label in ('caveat', 'irrelevant')
    normalized = _normalize_keyword_phrase(text)
    if normalized and any(phrase in normalized for phrase in _UNSUITABILITY_PHRASES):
        return True
    if preference_keywords:
        return _review_has_weakness_near_preference_keywords(text, preference_keywords)
    return _review_has_weakness_signal(text)
def _apply_llm_verdicts_to_quote_groups(supporting, caveats):
    """
    Re-bucket kutipan rerank/modal menurut verdict LLM.
    Tanpa verdict, bucket asal dipertahankan (rule tidak menimpa rerank).
    """
    out_supporting = []
    out_caveats = []
    seen = set()

    def push(row, default_bucket):
        if not isinstance(row, dict):
            return
        quote = str(row.get('quote') or '').strip()
        if len(quote) < _MIN_QUOTE_CHARS:
            return
        marker = clause_quote_key(quote)
        if not marker or marker in seen:
            return
        dest = _quote_destination(quote, default_bucket)
        if dest is None:
            return
        seen.add(marker)
        item = dict(row)
        item['quote'] = quote
        item['sentiment'] = dest
        verdict = _quote_llm_verdict(quote)
        if verdict is not None:
            item['sentiment_source'] = 'llm'
            item['sentiment_clause'] = verdict.get('clause') or ''
        if dest == 'caveat':
            out_caveats.append(item)
        else:
            out_supporting.append(item)

    for row in supporting or []:
        push(row, 'supporting')
    for row in caveats or []:
        push(row, 'caveat')
    return out_supporting, out_caveats
def _collect_modal_quote_groups(evidence, pills, search_keywords=None):
    """
    Kumpulkan kutipan modal lalu pisahkan berdasarkan sentimen terhadap preferensi.

    Return: (supporting, caveats)
      - supporting: kutipan yang cocok preferensi TANPA keluhan pada aspek itu,
        dipakai sebagai "bukti kecocokan".
      - caveats: kutipan yang cocok preferensi tetapi memuat keluhan pada aspek itu,
        dipakai sebagai "catatan dari ulasan" (bukan bukti kecocokan).
    """
    if not evidence:
        return [], []
    if evidence.get('llm_extracted') and (evidence.get('modal_display_quotes') or []):
        supporting = [
            dict(row) for row in (evidence.get('modal_display_quotes') or [])
            if isinstance(row, dict) and str(row.get('quote') or '').strip()
        ]
        caveats = [
            dict(row) for row in (evidence.get('modal_caveat_quotes') or [])
            if isinstance(row, dict) and str(row.get('quote') or '').strip()
        ]
        return _apply_llm_verdicts_to_quote_groups(supporting, caveats)
    search_keywords = _light_keyword_phrase_list(
        search_keywords or evidence.get('search_keywords') or [],
    )
    preference_keywords = _preference_keywords_for_evidence(pills, search_keywords)
    pill_set = {str(p).strip().lower() for p in (pills or []) if str(p).strip()}
    seen = set()
    candidates = []

    def _reason_ok(reason):
        if not reason or not str(reason).strip():
            return False
        return True

    def push(item):
        q = str(item.get('quote') or '').strip()
        if len(q) < _MIN_QUOTE_CHARS:
            return
        k = clause_quote_key(q)
        if not k or k in seen:
            return
        seen.add(k)
        candidates.append(dict(item))

    review_quotes = evidence.get('review_quotes') or []
    for item in review_quotes:
        pill = str(item.get('pill') or '').lower()
        if pill_set:
            if not (
                pill in pill_set
                or pill == 'search_keywords'
                or pill == 'semantic_match'
            ):
                continue
        reason = item.get('reason')
        if not _reason_ok(reason):
            continue
        push(item)

    for item in evidence.get('positive_review_quotes') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:4] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {**item, 'reason': reason, 'pill_label': item.get('pill_label') or 'Ulasan pengguna'}
        push(row)

    for item in evidence.get('search_keyword_matches') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:4] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {**item, 'reason': reason, 'pill_label': 'Kecocokan kata kunci'}
        push(row)

    for item in evidence.get('semantic_matches') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:3] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {
            **item,
            'reason': f'mirip makna: {reason}',
            'pill_label': 'Makna serupa',
            'match_source': 'semantic',
        }
        push(row)

    # Bucket negatif hanya masuk sebagai catatan, dan hanya bila kutipannya memang
    # menyentuh keyword preferensi (bukan sekadar review berating rendah).
    for item in evidence.get('negative_review_quotes') or []:
        terms = item.get('matched_terms') or []
        reason = ', '.join(str(t).strip() for t in terms[:4] if str(t).strip())
        if not _reason_ok(reason):
            continue
        row = {**item, 'reason': reason, 'pill_label': item.get('pill_label') or 'Catatan pengguna'}
        push(row)

    supporting = []
    caveats = []
    for item in _sort_quotes_for_modal_display(candidates):
        row = dict(item)
        verdict = _quote_llm_verdict(row.get('quote'))
        if verdict is not None:
            # Kutipan yang menurut LLM tidak membahas preferensi user sama sekali
            # dibuang: bukan bukti kecocokan, dan tidak layak jadi catatan.
            if str(verdict.get('label')) == 'irrelevant':
                continue
            row['sentiment_source'] = 'llm'
            row['sentiment_clause'] = verdict.get('clause') or ''
        if _quote_is_caveat(row.get('quote'), preference_keywords):
            row['sentiment'] = 'caveat'
            caveats.append(row)
        else:
            row['sentiment'] = 'supporting'
            supporting.append(row)

    meta_caveats = []
    for item in evidence.get('metadata_contradiction_quotes') or []:
        if not isinstance(item, dict):
            continue
        row = dict(item)
        row['sentiment'] = 'caveat'
        row['source'] = row.get('source') or 'metadata_contradiction'
        meta_caveats.append(row)
    if meta_caveats:
        caveats = _merge_caveat_quote_rows(meta_caveats, caveats, limit=max(2, len(caveats) + 2))
        support_keys = {_quote_marker_key(row.get('quote')) for row in caveats}
        supporting = [
            row for row in supporting
            if _quote_marker_key(row.get('quote')) not in support_keys
        ]
    return supporting, caveats
def _collect_modal_display_quotes(evidence, pills, search_keywords=None, limit=3):
    """Bukti kecocokan untuk modal: hanya kutipan relevan tanpa keluhan pada aspek itu."""
    if limit <= 0:
        return []
    supporting, _ = _collect_modal_quote_groups(
        evidence, pills, search_keywords=search_keywords,
    )
    return supporting[:limit]
def _build_modal_quote_summary_deterministic(shop_name, quotes, intent_phrase, evidence=None):
    """Fallback ringkasan modal (tanpa LLM)."""
    name = str(shop_name or 'Coffee shop ini').strip() or 'Coffee shop ini'
    if not quotes:
        # Jangan tampilkan pesan kosong-bukti; shop tanpa kutipan harus difilter dari output.
        return ''

    ev = evidence or {}
    reasons = []
    for q in quotes:
        r = str(q.get('reason') or '').strip()
        if r and r not in reasons:
            reasons.append(r)
        if len(reasons) >= 3:
            break
    themes = ', '.join(reasons[:2]) if reasons else 'pengalaman pengunjung'

    nums = []
    for q in quotes:
        try:
            if q.get('rating') is not None and q.get('rating') != '':
                nums.append(float(q['rating']))
        except (TypeError, ValueError):
            continue
    detail_parts = []
    avg_user_rating = ev.get('avg_user_rating')
    review_count = _safe_float(ev.get('review_count'))
    if avg_user_rating is not None:
        line = f'Rata-rata rating pengguna {float(avg_user_rating):.1f}/5'
        if review_count:
            line += f' dari {int(review_count)} ulasan'
        detail_parts.append(line)
    elif nums:
        detail_parts.append(f'Rata-rata rating pada kutipan di atas {sum(nums) / len(nums):.1f}/5')

    category_bits = []
    for key, label in (('suasana', 'suasana'), ('layanan', 'layanan'), ('makanan', 'makanan')):
        value = (ev.get('category_ratings') or {}).get(key)
        if value is not None:
            category_bits.append(f'{label} {float(value):.1f}')
    if category_bits:
        detail_parts.append('penilaian ' + ', '.join(category_bits))

    detail_line = (' ' + '; '.join(detail_parts) + '.') if detail_parts else ''

    ctx = str(intent_phrase or '').strip()
    if ctx:
        body = (
            f'{name} menurut ulasan pengunjung relevan untuk {ctx}, '
            f'terkait {themes}.{detail_line}'
        )
        return _normalize_whitespace(body)
    body = f'Pengunjung menyoroti {themes} tentang {name}.{detail_line}'
    return _normalize_whitespace(body)
def _relevant_quote_lines_for_prompt(evidence, *, limit=6, char_limit=260):
    """
    Baris kutipan review yang paling relevan dengan konteks preferensi user.
    Urutan sumber mengikuti kekuatan bukti: kutipan modal (sudah tersaring),
    lalu match keyword pencarian, lalu kutipan positif umum.
    """
    ev = evidence or {}
    lines = []
    seen = set()
    for key in (
        'modal_display_quotes',
        'search_keyword_matches',
        'review_quotes',
        'positive_review_quotes',
    ):
        for row in ev.get(key) or []:
            if len(lines) >= limit:
                return lines
            if not isinstance(row, dict):
                continue
            text = _normalize_whitespace(str(row.get('quote') or row.get('text') or ''))
            if len(text) < _MIN_QUOTE_CHARS:
                continue
            dedupe = clause_quote_key(text)
            if not dedupe or dedupe in seen:
                continue
            seen.add(dedupe)
            rating = row.get('rating')
            rating_text = str(rating) if rating not in (None, '') else '?'
            reason = _normalize_whitespace(str(row.get('reason') or ''))
            if not reason:
                terms = [
                    str(t).strip()
                    for t in (row.get('matched_terms') or row.get('keywords') or [])
                    if str(t).strip()
                ]
                reason = ', '.join(terms[:4])
            suffix = f' | relevan karena: {reason}' if reason else ''
            lines.append(
                f'  - (rating {rating_text}) "{_truncate_evidence_text(text, char_limit)}"{suffix}'
            )
    return lines
def _weakness_quote_lines_for_prompt(evidence, *, limit=2, char_limit=220):
    """
    Baris kutipan bernada kurang positif untuk bagian catatan.
    `modal_caveat_quotes` diprioritaskan karena keluhannya sudah terbukti menempel
    pada konteks preferensi user, bukan sekadar review berating rendah.
    """
    ev = evidence or {}
    rows = ev.get('modal_caveat_quotes') or ev.get('negative_review_quotes') or []
    lines = []
    for row in rows[:limit]:
        if not isinstance(row, dict):
            continue
        text = _normalize_whitespace(str(row.get('quote') or row.get('text') or ''))
        if len(text) < _MIN_QUOTE_CHARS:
            continue
        rating = row.get('rating')
        rating_text = str(rating) if rating not in (None, '') else '?'
        lines.append(f'  - (rating {rating_text}) "{_truncate_evidence_text(text, char_limit)}"')
    return lines
def _evidence_has_relevant_quotes(evidence, pills=None, search_keywords=None):
    """True jika ada minimal 1 kutipan PENDUKUNG (bukan hanya keluhan) untuk preferensi."""
    quotes = _collect_modal_display_quotes(
        evidence or {},
        pills,
        search_keywords=search_keywords,
        limit=1,
    )
    return len(quotes) > 0
def _build_modal_quote_summary(shop_name, quotes, intent_phrase, evidence=None, pills=None, search_keywords=None):
    """
    Ringkasan modal berbasis chat completion dari evidence review yang tersedia.
    Fallback ke ringkasan deterministik saat LLM tidak tersedia / gagal.
    """
    name = str(shop_name or 'Coffee shop ini').strip() or 'Coffee shop ini'
    ev = evidence or {}
    fallback_summary = _build_modal_quote_summary_deterministic(name, quotes, intent_phrase, evidence=ev)

    if not llm_is_available():
        LOG_RECOMMEND.warning(f"Modal quote summary: LLM off, fallback ({name})")
        return fallback_summary

    LOG_RECOMMEND.info(f"Modal quote summary: panggil LLM untuk '{name}'...")
    modal_t0 = time.perf_counter()

    pill_stats = ev.get('pill_stats') or []
    facilities_tab = ev.get('facilities_tab_intent') or ev.get('facilities_tab') or {}
    facilities_intent_aligned = bool(ev.get('facilities_intent_aligned'))
    ctx = str(intent_phrase or '').strip() or 'preferensi umum'
    keyword_line = ", ".join(_light_keyword_phrase_list(search_keywords or [])) or 'tidak ada'
    profile_lines = _shop_profile_lines_for_prompt({}, ev, pills=pills) or ['  - (tidak ada data rating)']

    stats_lines = []
    for item in pill_stats[:6]:
        if not isinstance(item, dict):
            continue
        label = str(item.get('pill_label') or item.get('pill') or '').strip() or 'konteks'
        hits = item.get('keyword_review_hits')
        cat_field = item.get('category_field')
        cat_avg = item.get('category_avg')
        line = f"  - {label}: {hits} ulasan menyebut kata terkait"
        if cat_field and cat_avg is not None:
            line += f", rata-rata {cat_field} {cat_avg}/5"
        stats_lines.append(line)
    if not stats_lines:
        stats_lines = ['  - (tidak ada statistik pill)']

    facility_lines = []
    for key, label in (('popular_for', 'Populer untuk'), ('highlights', 'Keunggulan'), ('atmosphere', 'Suasana')):
        values = facilities_tab.get(key) or []
        if values:
            facility_lines.append(f"  - {label}: {', '.join(str(v) for v in values[:6])}")
    if facility_lines and facilities_intent_aligned:
        facility_lines.append('  - (sinyal fasilitas di atas selaras dengan preferensi user)')
    if not facility_lines:
        facility_lines = ['  - (tidak ada sinyal fasilitas tab)']
    gate = ev.get('metadata_gate') or {}
    matched_labels = [
        str(x) for x in (gate.get('matched_attribute_labels') or []) if x
    ]
    if matched_labels:
        facility_lines.append(
            '  - Profil fasilitas resmi selaras pill user: ' + ', '.join(matched_labels)
        )
    hours = str(ev.get('opening_hours_display') or '').strip()
    if hours:
        facility_lines.append(f'  - Jam operasional toko (database): {hours}')

    # Bukti kecocokan dan keluhan dipisah: kutipan yang memuat keluhan pada aspek
    # preferensi tidak boleh jadi alasan merekomendasikan.
    supporting_source = (
        {'modal_display_quotes': ev.get('modal_display_quotes') or []}
        if ev.get('modal_display_quotes')
        else ev
    )
    quote_lines = _relevant_quote_lines_for_prompt(supporting_source, limit=6, char_limit=300)
    if not quote_lines:
        quote_lines = ['  - (tidak ada kutipan review yang bisa diringkas)']

    prompt = f"""Anda meringkas ulasan SATU coffee shop secara objektif (orang ketiga).
Tulis 1 paragraf 3-4 kalimat padat berdasarkan kutipan di bawah. Jangan menyalin kata saya/aku/kami.

Syarat:
- Kalimat pertama: nama {name} + kebutuhan "{ctx}" hanya jika kutipan mendukung
- 1-2 detail konkret dari kutipan (bukan hanya nyaman/cozy)
- Satu paragraf, tanpa markdown, tanpa mengarang fakta

Nama coffee shop: {name}
Kebutuhan user: {ctx}
Keyword intent: {keyword_line}
Pill preferensi: {", ".join(pills or []) if pills else "tidak ada"}

Profil dari database:
{chr(10).join(profile_lines)}

Seberapa sering konteks ini dibahas:
{chr(10).join(stats_lines)}

Sinyal fasilitas:
{chr(10).join(facility_lines)}

Kutipan ulasan paling relevan dengan konteks:
{chr(10).join(quote_lines)}"""
    prompt = _compact_prompt_block(prompt, 5600)

    try:
        raw = llm_chat_completions_create(
            model=(HF_MODEL or "meta-llama/Meta-Llama-3-8B").strip(),
            messages=[
                {
                    'role': 'system',
                    'content': (
                        'Anda merangkum SATU coffee shop dari ulasan. '
                        'Orang ketiga, 3-4 kalimat padat, hanya fakta dari data kutipan.'
                    ),
                },
                {'role': 'user', 'content': prompt},
            ],
            max_tokens=400,
            temperature=0.4,
        )
        summary = _normalize_whitespace(str(raw or ''))
        if summary.startswith('```'):
            summary = re.sub(r'^```[a-zA-Z]*\s*', '', summary).strip()
            summary = re.sub(r'\s*```$', '', summary).strip()
        # Prompt modal tidak lagi mewajibkan format label; cukup validasi teks natural.
        if not summary:
            return fallback_summary
        lowered = summary.lower()
        if lowered.startswith('{') or lowered.startswith('[') or '```' in summary or 'json' in lowered:
            return fallback_summary
        sentence_parts = [
            part.strip()
            for part in re.split(r'(?<=[.!?])\s+', summary)
            if part.strip()
        ]
        if not sentence_parts:
            return fallback_summary
        if len(sentence_parts) > 4:
            summary = ' '.join(sentence_parts[:4]).strip()
            if summary and summary[-1] not in '.!?':
                summary += '.'
        LOG_RECOMMEND.info(
            f"Modal quote summary: OK '{name}' "
            f"({round((time.perf_counter() - modal_t0) * 1000, 1)} ms)")
        return summary
    except Exception as err:
        LOG_RECOMMEND.warning(
            f"Modal quote summary LLM fallback triggered ({name}): {err}")
        return fallback_summary
def _attach_modal_evidence_to_supporting(evidence, shop_name, pills, search_keywords=None):
    """Salin evidence dan tambah modal_display_quotes, modal_caveat_quotes, modal_quote_summary."""
    ev = dict(evidence or {})
    if ev.get('llm_extracted') and (ev.get('modal_display_quotes') or []):
        if COFIND_MODAL_QUOTE_LLM and not ev.get('modal_quote_summary'):
            pill_labels = [PILL_LABELS.get(p, p) for p in (pills or [])]
            intent_phrase = ' dan '.join(pill_labels[:3]) if pill_labels else ''
            ev['modal_quote_summary'] = _build_modal_quote_summary(
                shop_name,
                ev.get('modal_display_quotes') or [],
                intent_phrase,
                evidence=ev,
                pills=pills,
                search_keywords=search_keywords,
            )
        else:
            ev.setdefault('modal_quote_summary', '')
        return ev

    quotes = list(ev.get('modal_display_quotes') or [])[:3]
    if not quotes:
        quotes = list(ev.get('review_quotes') or [])[:3]
    ev['modal_display_quotes'] = quotes
    ev['modal_caveat_quotes'] = list(ev.get('modal_caveat_quotes') or [])[:2]
    pill_labels = [PILL_LABELS.get(p, p) for p in (pills or [])]
    intent_phrase = ' dan '.join(pill_labels[:3]) if pill_labels else ''
    # Opsional via COFIND_MODAL_QUOTE_LLM=true. Saat mati, biarkan kosong supaya modal
    # memakai `explanation` (ringkasan LLM berbasis seluruh korpus review) yang jauh
    # lebih informatif ketimbang kalimat template deterministik.
    if COFIND_MODAL_QUOTE_LLM:
        ev['modal_quote_summary'] = _build_modal_quote_summary(
            shop_name,
            quotes,
            intent_phrase,
            evidence=ev,
            pills=pills,
            search_keywords=search_keywords,
        )
    else:
        ev['modal_quote_summary'] = ''
    return ev
def _quote_has_activity_or_semantic_link(row, pills, search_keywords=None):
    """True jika kutipan terhubung ke aktivitas, rerank, atau gerbang makna."""
    if not isinstance(row, dict):
        return False
    pill = str(row.get('pill') or '').strip().lower()
    if row.get('match_source') == 'semantic' or pill == 'semantic_match':
        return True
    if row.get('llm_extracted') or row.get('supporting_index'):
        return True
    activity_pills, _ = _split_preference_pills(pills)
    activity_set = {str(p).strip().lower() for p in activity_pills if p}
    if pill and pill in activity_set:
        return True
    if row.get('matched_terms'):
        return True
    text = str(row.get('quote') or '')
    keywords = _preference_keywords_for_evidence(activity_pills or pills, search_keywords)
    return any(_matches_keyword_phrase(text, keyword) for keyword in keywords)
def _quote_texts_for_coverage(shop):
    """Korpus teks untuk coverage: semua kutipan evidence + teks review profil."""
    seen = set()
    texts = []

    def _add(raw):
        text = str(raw or '').strip()
        if len(text) < 6:
            return
        key = text[:180].lower()
        if key in seen:
            return
        seen.add(key)
        texts.append(text)

    for chunk in _iter_shop_quote_texts(shop):
        _add(chunk)
    profile = shop.get('profile') if isinstance(shop.get('profile'), dict) else {}
    for review in profile.get('reviews') or []:
        if isinstance(review, dict):
            _add(review.get('text') or review.get('review_text') or review.get('body'))
    return texts
