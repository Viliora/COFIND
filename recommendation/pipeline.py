"""Generator event pipeline rekomendasi pill / free-text."""
from __future__ import annotations

from recommendation.wiring import ensure_recommendation_wiring, populate_pipeline_namespace

ensure_recommendation_wiring()
populate_pipeline_namespace(globals())


def _recommendation_progress(stage, **extra):
    payload = dict(
        _RECOMMENDATION_PROGRESS_BY_STAGE.get(stage)
        or {'stage': stage, 'percent': 0, 'next_percent': 100, 'label': ''}
    )
    payload.update(extra)
    return ('progress', payload)


def recommendation_pipeline_events(prefs, _auth_user, query_text=''):
    """
    Pipeline RAG 3 fase. Dua jalur input SALING EKSKLUSIF per request:

      A. Jalur pill (seperti sebelumnya): `prefs` berisi pill aktivitas +
         atribut fasilitas dari PILL_MAPPING.
      B. Jalur free text: `query_text` (maks FREE_TEXT_MAX_CHARS) → LLM intent
         (keywords + dense_query); output langsung ke hybrid retrieval yang
         sama (BM25 + dense/ANN → RRF). Tidak ada upgrade otomatis ke pill.

      Fase 1 — Hard filter: wajib minimal 1 ulasan pipeline (Cofind + Google Places,
               get_reviews_for_recommendation_batch / REVIEW_BASED_MIN_REVIEWS=1).
      Fase 2 — Hybrid retrieval + evidence + ABSA kutipan (BM25 + dense/ANN → RRF;
               sentimen klausa damasukma/indobert-absa + triase e5/Jina).
               Top ~7 ke rerank.
      Fase 3 — Cross-encoder rerank (Jina): pilih 0–3 toko, kutipan pendukung/caveat.

      Feedback thumbs (helpful / not_helpful) disimpan via API feedback ke DB untuk
      analitik, evaluasi admin, dan UI modal — tidak mem-filter toko di Fase 1/2/3.

    Generator: yield ('progress', payload) di tiap batas tahap, lalu tepat satu
    ('result', (body_dict, status_code)) di akhir. Autentikasi dan parsing body
    dilakukan pemanggil supaya generator ini bebas dari request context Flask.
    """
    request_t0 = time.perf_counter()
    stage_t0 = request_t0
    stage_ms = {}
    clause_sentiment_token = None
    clause_sentiment_telemetry = {}
    semantic_budget_token = begin_semantic_encode_budget()
    llm_usage_token = None
    llm_route_token = None
    llm_run_route = None
    pipeline_run_id = None
    try:
        ensure_recommendation_wiring()
        pipeline_run_id = new_pipeline_run_id()
        llm_usage_token = begin_llm_usage_collection()
        llm_route_token = begin_llm_run_route()

        query_text = str(query_text or '').strip()[:FREE_TEXT_MAX_CHARS]
        has_pills_input = bool(prefs)
        has_query_text = bool(query_text)

        if not has_pills_input and not has_query_text:
            yield ('result', ({
                'status': 'error',
                'message': 'Pilih pill preferensi atau isi kata kunci pencarian.',
            }, 400))
            return
        if has_pills_input and has_query_text:
            # Frontend menjaga eksklusivitas pill vs free text; ini jaring kedua
            # defensif di backend bila klien lama/custom mengirim keduanya.
            yield ('result', ({
                'status': 'error',
                'message': 'Kirim salah satu: pill preferensi atau kata kunci pencarian, tidak keduanya.',
            }, 400))
            return

        free_text_keywords = []
        free_text_dense_query = ''
        free_text_telemetry = {}
        user_intent_line = ''
        free_text_query_handling = {}
        free_text_response_message = None
        free_text_summary_framing = None

        if has_pills_input:
            valid_pills = [p for p in prefs if p in PILL_MAPPING]
            if not valid_pills:
                yield ('result', ({
                    'status': 'error',
                    'message': f'Preferensi tidak dikenali: {", ".join(prefs)}',
                }, 400))
                return
        else:
            # --- Jalur free text: deteksi intent via LLM sebelum Fase 2 ---
            yield _recommendation_progress('intent')
            intent_t0 = time.perf_counter()
            intent_result = extract_search_intent(
                query_text,
                pill_labels=PILL_LABELS,
                pill_mapping=PILL_MAPPING,
                chat_fn=_llm_chat_for_pipeline,
                parse_json_fn=_parse_llm_json_with_repair,
            )
            stage_ms['intent_ms'] = round((time.perf_counter() - intent_t0) * 1000, 1)
            free_text_telemetry = intent_result.get('telemetry') or {}
            free_text_telemetry['intent_hint_pill'] = intent_result.get('matched_pill')
            free_text_telemetry['intent_hint_attributes'] = (
                intent_result.get('matched_attribute_pills') or []
            )
            free_text_query_handling = merge_query_classification(
                query_text,
                llm_query_class=intent_result.get('query_class'),
                impossible_detail=intent_result.get('impossible_detail'),
                alternative_keywords=intent_result.get('alternative_keywords'),
            )
            free_text_telemetry['query_class'] = free_text_query_handling.get('query_class')
            free_text_response_message = free_text_query_handling.get('response_message')
            free_text_summary_framing = free_text_query_handling.get('summary_framing')
            LOG_RECOMMEND.info(
                f"Free text intent: query={query_text!r} backend={free_text_telemetry.get('backend')} "
                f"hint_pill={intent_result.get('matched_pill')} "
                f"keywords={intent_result.get('keywords')} "
                f"query_class={free_text_telemetry.get('query_class')}"
            )

            if free_text_query_handling.get('early_exit'):
                yield ('result', ({
                    'status': 'success',
                    'message': free_text_response_message,
                    'recommendations': [],
                    'query_handling': {
                        'class': free_text_query_handling.get('query_class'),
                    },
                }, 200))
                return

            valid_pills = []
            user_intent_line = query_text
            free_text_keywords = [
                str(k).strip() for k in (intent_result.get('keywords') or []) if str(k or '').strip()
            ]
            free_text_dense_query = str(intent_result.get('dense_query') or '').strip() or query_text

            if free_text_query_handling.get('query_class') == QUERY_CLASS_FALSE_PRESUP:
                adjusted = apply_false_presupposition_retrieval(
                    raw_query=query_text,
                    keywords=free_text_keywords,
                    dense_query=free_text_dense_query,
                    alternative_keywords=free_text_query_handling.get('alternative_keywords') or [],
                )
                free_text_keywords = adjusted['keywords']
                free_text_dense_query = adjusted['dense_query']

            if (
                free_text_query_handling.get('query_class') == QUERY_CLASS_NEGATIVE
                and not free_text_keywords
            ):
                free_text_keywords = ['rating', 'keluhan']
                free_text_dense_query = 'coffee shop dengan rating rendah dan keluhan di ulasan'

            if not free_text_keywords:
                yield ('result', ({
                    'status': 'success',
                    'message': 'Kata kunci terlalu umum, coba kata kunci lain atau pilih pill preferensi.',
                    'recommendations': [],
                }, 200))
                return

        if COFIND_DEV_LLM_STRICT and not llm_is_available():
            yield ('result', ({
                'status': 'error',
                'message': 'LLM strict mode aktif tetapi LLM tidak tersedia.',
                'recommendations': [],
            }, 503))
            return

        llm_run_route = probe_llm_for_recommendation_run()
        stage_ms['llm_run_route'] = llm_run_route.mode
        stage_ms['llm_probe_reason'] = llm_run_route.reason
        if llm_run_route.hf_error_snippet:
            stage_ms['llm_probe_hf_error'] = llm_run_route.hf_error_snippet[:120]
        route_log = (
            f"LLM route run: {llm_run_route.mode} (reason={llm_run_route.reason})"
        )
        if llm_run_route.hf_error_snippet and llm_run_route.mode == 'gemini':
            route_log += f" hf_err={llm_run_route.hf_error_snippet[:100]}"
        LOG_RECOMMEND.info(route_log)
        if llm_run_route.mode == 'off':
            LOG_RECOMMEND.info(
                "LLM probe: fase LLM (rerank/sentiment/summary) memakai fallback "
                "hybrid/deterministik untuk run ini."
            )

        activity_pills, attribute_pills = _split_preference_pills(valid_pills)
        LOG_RECOMMEND.info(f"Pills: {valid_pills}")
        yield _recommendation_progress('start')

        # Umpan balik not_helpful (thumbs-down) dicatat ke DB lewat
        # /api/recommend-by-preferences/feedback (upsert_recommendation_feedback) untuk
        # analitik, ringkasan admin, dan state UI modal — BUKAN filter hard retrieval.
        # Toko yang pernah not_helpful tetap diload di Fase 1 (_build_profiles_for_recommendation
        # tanpa excluded_place_ids dari feedback). Jika LLM rerank memilih toko itu lagi,
        # rekomendasi tetap dikirim ke client.

        # Konteks personalisasi (review sendiri + favorit) untuk tahap keputusan LLM.
        taste_profile = build_user_taste_profile(_auth_user.get('id'))
        user_taste_block = format_user_taste_prompt_block(taste_profile)

        all_place_ids = _load_all_place_ids()
        if not all_place_ids:
            yield ('result', ({'status': 'error', 'message': 'Data coffee shop kosong.'}, 500))
            return
        facilities_index = load_facilities_index()

        MAX_REC = 3

        # --- Fase 1: hard filter (min review pipeline; bukan exclude not_helpful) ---
        LOG_RECOMMEND.info("Fase 1: batch load profil + reviews...")
        profiles, shops_without_reviews = _build_profiles_for_recommendation(
            all_place_ids,
            facilities_index=facilities_index,
        )
        LOG_RECOMMEND.info(
            f"Fase 1 selesai: profiles={len(profiles)} "
            f"tanpa_review={len(shops_without_reviews)}")
        stage_ms['profile_load_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        yield _recommendation_progress('profiles', shops_with_reviews=len(profiles))

        # --- Fase 2: Hybrid retrieval (BM25 + dense/ANN → RRF) ---
        quality_by_place = {
            str(profile.get('place_id')): _quality_score_for_profile(profile)
            for profile in profiles
            if profile.get('place_id')
        }
        if has_pills_input:
            retrieval = retrieve_top_k(
                profiles,
                valid_pills,
                pill_labels=PILL_LABELS,
                pill_mapping=PILL_MAPPING,
                quality_by_place=quality_by_place,
                top_k=retrieval_top_k(),
                activity_pills=activity_pills,
                attribute_pills=attribute_pills,
            )
        elif (
            has_query_text
            and free_text_query_handling.get('query_class') == QUERY_CLASS_NEGATIVE
        ):
            retrieval = retrieve_top_k_by_negative_sentiment(
                profiles,
                quality_by_place=quality_by_place,
                top_k=retrieval_top_k(),
            )
        else:
            retrieval = retrieve_top_k_by_text(
                profiles,
                query_tokens=free_text_keywords,
                dense_query_text=free_text_dense_query,
                quality_by_place=quality_by_place,
                top_k=retrieval_top_k(),
            )
        retrieval_telemetry = dict(retrieval.get('telemetry') or {}, free_text=free_text_telemetry)
        query_tokens = retrieval.get('query_tokens') or []
        # NB: `query_text` di sini SENGAJA menimpa parameter free-text mentah di
        # atas — dari titik ini sampai akhir fungsi, `query_text` berarti teks
        # dense query hasil retrieval (konsisten dengan jalur pill sebelumnya).
        query_text = retrieval.get('query_text') or ''
        activity_tokens = retrieval.get('activity_tokens') or []
        attribute_tokens = retrieval.get('attribute_tokens') or []
        activity_query_text = retrieval.get('activity_query_text') or query_text
        activity_matcher = retrieval.get('activity_matcher') or compile_activity_matcher(
            activity_pills, pill_labels=PILL_LABELS, pill_mapping=PILL_MAPPING,
        )
        search_keywords = query_tokens
        scored_candidates = []
        for item in retrieval.get('candidates') or []:
            profile = item.get('profile') or {}
            score_detail = dict(item.get('score_detail') or {})
            keyword_detail = _score_shop_by_user_reviews(
                profile, valid_pills, search_keywords=query_tokens,
            )
            score_detail['per_pill_stats'] = keyword_detail.get('per_pill_stats') or {}
            retrieval_ev = _build_retrieval_evidence(
                profile,
                valid_pills,
                query_text=query_text,
                query_tokens=query_tokens,
                activity_tokens=activity_tokens,
                activity_query_text=activity_query_text,
                attribute_tokens=attribute_tokens,
                activity_matcher=activity_matcher,
                activity_pills=activity_pills,
                attribute_pills=attribute_pills,
            )
            review_ev = _build_review_based_evidence(
                profile, score_detail, valid_pills, search_keywords=query_tokens,
            )
            retrieval_ev['pill_stats'] = review_ev.get('pill_stats') or []
            if review_ev.get('positive_review_quotes'):
                retrieval_ev['positive_review_quotes'] = _merge_quote_rows(
                    retrieval_ev.get('positive_review_quotes'),
                    review_ev.get('positive_review_quotes'),
                )
            attached_evidence = _attach_metadata_gate_to_evidence(
                retrieval_ev,
                score_detail=score_detail,
                metadata_gate=item.get('metadata_gate'),
                reviews=(profile.get('reviews') or []),
            )
            attached_evidence['metadata_support'] = _build_metadata_support_items(
                attached_evidence,
                facilities_tab_intent=review_ev.get('facilities_tab_intent') or {},
                facilities_intent_aligned=review_ev.get('facilities_intent_aligned'),
            )
            shop = {
                'place_id': item.get('place_id'),
                'name': item.get('name') or profile.get('name') or '',
                'score': item.get('score', 0),
                'profile': profile,
                'score_detail': score_detail,
                'evidence': _enrich_evidence_with_profile_context(
                    attached_evidence,
                    profile,
                ),
            }
            _attach_pill_coverage(shop, valid_pills)
            scored_candidates.append(shop)
        sentiment_t0 = time.perf_counter()
        verdicts, clause_sentiment_telemetry = _run_clause_sentiment_for_candidates(
            scored_candidates, valid_pills,
        )
        if verdicts:
            clause_sentiment_token = _set_clause_verdicts(verdicts)
        stage_ms['clause_sentiment_ms'] = round((time.perf_counter() - sentiment_t0) * 1000, 1)
        stage_ms['hybrid_retrieval_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_t0 = time.perf_counter()
        LOG_RECOMMEND.info(
            f"Fase 2 selesai: {len(scored_candidates)}/{retrieval_telemetry.get('kept_with_signal', 0)} "
            f"kandidat (gated={retrieval_telemetry.get('activity_gated')}, "
            f"lex={retrieval_telemetry.get('activity_pass_lexical', 0)}, "
            f"dense_only={retrieval_telemetry.get('activity_pass_dense_only', 0)}, "
            f"rejected={retrieval_telemetry.get('activity_rejected', 0)}, "
            f"meta_prior={retrieval_telemetry.get('metadata_prior_applied', 0)}, "
            f"meta_penalty={retrieval_telemetry.get('metadata_penalized', 0)}) "
            f"bm25_shops={retrieval_telemetry.get('bm25_shops')}, "
            f"dense={retrieval_telemetry.get('dense')})")
        if clause_sentiment_telemetry.get('skipped'):
            LOG_RECOMMEND.info(
                f"ABSA kutipan dilewati: {clause_sentiment_telemetry.get('skipped')}")
        else:
            LOG_RECOMMEND.info(
                f"ABSA kutipan: quotes={clause_sentiment_telemetry.get('quotes', 0)} "
                f"verdicts={clause_sentiment_telemetry.get('verdicts', 0)} "
                f"absa={clause_sentiment_telemetry.get('from_absa', 0)}")
        yield _recommendation_progress('scoring', candidates=len(scored_candidates))

        if not scored_candidates:
            yield _recommendation_progress('done', shortlisted=0)
            yield ('result', ({
                'status': 'success',
                'message': _MANUAL_UNCLEAR_MESSAGE,
                'recommendations': [],
            }, 200))
            return

        # --- Fase 3: cross-encoder rerank + kutipan (fallback: urutan hybrid) ---
        rerank_backend = 'hybrid'
        rerank_telemetry = {}
        ranked_candidates = scored_candidates
        keyword_line = query_text or ', '.join(query_tokens[:20])
        if free_text_summary_framing:
            keyword_line = f'{keyword_line}\n\n[Framing respons]\n{free_text_summary_framing}'
        if scored_candidates and ce_rerank_enabled():
            rerank_pool = scored_candidates[:llm_rerank_pool()]
            rerank_user_id = _auth_user.get('id')
            cached_fits = _get_cached_rerank_fits(
                rerank_pool,
                valid_pills,
                user_id=rerank_user_id,
                search_keywords=query_tokens,
            )
            rerank_result = ce_rerank_candidates(
                scored_candidates,
                valid_pills,
                pill_labels=PILL_LABELS,
                user_taste_block=user_taste_block,
                keyword_line=keyword_line,
                cached_fits=cached_fits,
                max_candidates=retrieval_top_k(),
                activity_pills=activity_pills,
                activity_tokens=activity_tokens,
                activity_matcher=activity_matcher,
                activity_query_text=activity_query_text,
            ) or {}
            rerank_telemetry = rerank_result.get('telemetry') or {}
            if rerank_result.get('ranked'):
                ranked_candidates = rerank_result['ranked']
                rerank_backend = rerank_telemetry.get('backend') or 'cross_encoder'
                if not cached_fits:
                    _store_rerank_fits(
                        rerank_pool,
                        valid_pills,
                        rerank_result.get('fits') or {},
                        user_id=rerank_user_id,
                        search_keywords=query_tokens,
                    )
            else:
                LOG_RECOMMEND.warning(
                    f"Fase 3: CE rerank tidak dipakai "
                    f"({rerank_telemetry.get('backend')}: {rerank_telemetry.get('error')})")

        top_shops = _select_top_shops(
            ranked_candidates,
            max_rec=max(MAX_REC, retrieval_top_k()),
            activity_tokens=activity_tokens,
            activity_pills=activity_pills,
            activity_matcher=activity_matcher,
        )
        kept = []
        dropped_activity = 0
        for shop in top_shops:
            _apply_llm_extracted_quotes(
                shop, valid_pills,
                activity_tokens=activity_tokens,
                activity_matcher=activity_matcher,
            )
            if _shop_has_activity_contradiction(
                shop, activity_pills, activity_tokens, activity_matcher=activity_matcher,
            ):
                dropped_activity += 1
                LOG_RECOMMEND.info(
                    f"Drop {shop.get('name')}: kutipan menolak aktivitas "
                    f"{[PILL_LABELS.get(p, p) for p in activity_pills]}"
                )
                continue
            evidence = shop.get('evidence') or {}
            caveat_rows = list(evidence.get('modal_caveat_quotes') or [])
            caveat_keys = {
                clause_quote_key(row.get('quote') if isinstance(row, dict) else row)
                for row in caveat_rows
            }
            display = _supporting_quotes_without_activity_contradiction(
                evidence.get('modal_display_quotes') or [],
                activity_pills,
                activity_tokens,
                activity_matcher=activity_matcher,
            )
            display = [
                row for row in display
                if clause_quote_key(
                    row.get('quote') if isinstance(row, dict) else row
                ) not in caveat_keys
            ]
            if not display:
                display = _activity_quotes_from_reviews(
                    shop, activity_matcher, activity_tokens, limit=3,
                )
            if attribute_pills and len(display) < 3:
                existing = {
                    clause_quote_key(row.get('quote') if isinstance(row, dict) else row)
                    for row in display
                }
                for row in _attribute_quote_rows(evidence, attribute_pills, limit=3):
                    if len(display) >= 3:
                        break
                    key = clause_quote_key(row.get('quote'))
                    if not key or key in existing:
                        continue
                    existing.add(key)
                    display.append(row)
            evidence['modal_display_quotes'] = display
            shop['evidence'] = evidence
            if not display:
                LOG_RECOMMEND.info(
                    f"Keep {shop.get('name')}: bukti aktivitas tanpa kutipan fasilitas"
                )
            _attach_pill_coverage(shop, valid_pills)
            kept.append(shop)
            if len(kept) >= MAX_REC:
                break
        top_shops = kept
        if dropped_activity:
            LOG_RECOMMEND.info(
                f"Fase 3: {dropped_activity} toko dibuang karena kontradiksi aktivitas"
            )
        stage_ms['rerank_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_ms['rerank_backend'] = rerank_backend
        stage_t0 = time.perf_counter()
        LOG_RECOMMEND.info(
            f"Fase 3: {len(top_shops)}/{MAX_REC} toko dari rerank={rerank_backend} "
            f"(kandidat dinilai LLM={rerank_telemetry.get('scored_by_llm', 0)}, "
            f"kutipan tidak tergrounding={rerank_telemetry.get('ungrounded_quotes', 0)})")
        for rank, shop in enumerate(top_shops, 1):
            fit = shop.get('llm_fit') or {}
            LOG_RECOMMEND.debug(
                f"#{rank} {shop.get('name')} score={shop.get('score')} "
                f"final={shop.get('final_score', shop.get('score'))} "
                f"llm_fit={fit.get('fit_score')}")

        yield _recommendation_progress('rerank', shortlisted=len(top_shops))

        if not top_shops:
            yield _recommendation_progress('done', shortlisted=0)
            yield ('result', ({
                'status': 'success',
                'message': _MANUAL_UNCLEAR_MESSAGE,
                'recommendations': [],
            }, 200))
            return

        # --- Step 5: LLM NLP summary wajib mengutip review ---
        LOG_RECOMMEND.info(
            f"Step 5: generate summary untuk {len(top_shops)} shop...")
        yield _recommendation_progress('summary', shortlisted=len(top_shops))
        recommendations, summary_stats = _generate_llm_review_summary(
            top_shops,
            valid_pills,
            search_keywords=query_tokens,
            user_intent_line=user_intent_line or None,
            summary_framing=free_text_summary_framing,
        )
        stage_ms['llm_summary_ms'] = round((time.perf_counter() - stage_t0) * 1000, 1)
        stage_ms['summary_llm_count'] = summary_stats.get('summary_llm_count')
        stage_ms['summary_fallback_count'] = summary_stats.get('summary_fallback_count')
        stage_ms['total_ms'] = round((time.perf_counter() - request_t0) * 1000, 1)
        token_usage = summarize_llm_usage()
        stage_ms['llm_prompt_tokens'] = token_usage.get('prompt_tokens')
        stage_ms['llm_completion_tokens'] = token_usage.get('completion_tokens')
        stage_ms['llm_total_tokens'] = token_usage.get('total_tokens')
        degradation = build_degradation_snapshot(
            llm_available=_llm_ready_for_recommend_run(),
            clause_sentiment_telemetry=clause_sentiment_telemetry,
            rerank_backend=rerank_backend,
            rerank_telemetry=rerank_telemetry,
            delivered_count=len(recommendations),
            summary_fallback_count=int(
                summary_stats.get('summary_fallback_count') or 0
            ),
        )
        dense_tel = retrieval_telemetry.get('dense') or {}
        pipeline_snapshot = dict(degradation)
        pipeline_snapshot['hybrid_retrieval_ms'] = stage_ms.get('hybrid_retrieval_ms')
        pipeline_snapshot['dense_pool'] = dense_tel.get('pool')
        pipeline_snapshot['dense_store'] = dense_tel.get('store')
        pipeline_snapshot['ann_reviews'] = dense_tel.get('ann_reviews')
        prefs_key = preferences_key_from_pills(valid_pills)
        metric_payload = {
            'run_id': pipeline_run_id,
            'user_id': _auth_user.get('id'),
            'preferences_key': prefs_key,
            'status': 'success',
            'delivered_count': len(recommendations),
            'stage_ms': stage_ms,
            'token_usage': token_usage,
            'degradation': degradation,
            'retrieval': {
                'metadata_prior_applied': retrieval_telemetry.get('metadata_prior_applied'),
                'metadata_penalized': retrieval_telemetry.get('metadata_penalized'),
            },
        }
        log_recommendation_run_json(metric_payload)
        record_pipeline_run(
            run_id=pipeline_run_id or new_pipeline_run_id(),
            user_id=_auth_user.get('id'),
            preferences_key=prefs_key,
            status='success',
            delivered_count=len(recommendations),
            stage_ms=stage_ms,
            retrieval_telemetry=retrieval_telemetry,
            snapshot=pipeline_snapshot,
            token_usage=token_usage,
        )
        LOG_METRIC.info(f"recommend_by_preferences {stage_ms}")
        LOG_RECOMMEND.info(
            f"Selesai: {len(recommendations)} rekomendasi dikirim ke client "
            f"(run_id={pipeline_run_id}, llm_tokens={token_usage.get('total_tokens')})")

        yield _recommendation_progress('done', delivered=len(recommendations))
        result_body = {
            'status': 'success',
            'preferences': valid_pills,
            'preference_activities': [p for p in valid_pills if p not in FACILITY_ATTRIBUTE_PILLS],
            'preference_attributes': [p for p in valid_pills if p in FACILITY_ATTRIBUTE_PILLS],
            'search_keywords': search_keywords,
            'llm_pipeline': {
                'run_id': pipeline_run_id,
                'config': full_pipeline_config(),
                'degradation': degradation,
                'token_usage': token_usage,
                'stage_ms': dict(stage_ms),
                'retrieval': dict(retrieval_telemetry),
                'rerank': dict(rerank_telemetry, backend=rerank_backend),
                'clause_sentiment': dict(
                    clause_sentiment_config(),
                    **clause_sentiment_telemetry,
                ),
                'personalization_used': bool(user_taste_block),
                'semantic': dict(
                    semantic_gate_config(),
                    model_ready=semantic_model_available(),
                    budget=semantic_encode_budget_state(),
                ),
            },
            'recommendations': recommendations,
        }
        if free_text_response_message:
            result_body['message'] = free_text_response_message
        if free_text_query_handling.get('query_class'):
            result_body['query_handling'] = {
                'class': free_text_query_handling.get('query_class'),
                'impossible_detail': free_text_query_handling.get('impossible_detail'),
            }
        yield ('result', (result_body, 200))

    except Exception as e:
        LOG_RECOMMEND.exception("Pipeline rekomendasi gagal")
        yield ('result', ({'status': 'error', 'message': str(e), 'recommendations': []}, 500))
    finally:
        _reset_clause_verdicts(clause_sentiment_token)
        reset_semantic_encode_budget(semantic_budget_token)
        if llm_route_token is not None:
            reset_llm_run_route(llm_route_token)
        if llm_usage_token is not None:
            reset_llm_usage_collection(llm_usage_token)
        # Vektor & verdict baru ditulis ke lapis file sekali per request, bukan
        # per kalimat, supaya request berikutnya tidak menghitung ulang.
        for flush_fn in (flush_semantic_cache, flush_clause_sentiment_cache):
            try:
                flush_fn()
            except Exception as flush_err:
                LOG_RECOMMEND.warning(f"Gagal flush cache: {str(flush_err)[:120]}")
        try:
            if 'total_ms' not in stage_ms:
                stage_ms['total_ms'] = round((time.perf_counter() - request_t0) * 1000, 1)
            stage_ms.setdefault('rerank_backend', 'none')
            LOG_METRIC.info(f"recommend_by_preferences_final {stage_ms}")
        except Exception as metric_err:
            # Telemetry tidak boleh menggagalkan request yang sudah selesai.
            LOG_METRIC.debug(f"Gagal menulis metrik akhir: {metric_err}")
