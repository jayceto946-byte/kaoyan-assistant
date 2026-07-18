import threading


def _run_threads(targets):
    threads = [threading.Thread(target=target) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=5)
    assert all(not thread.is_alive() for thread in threads)


def test_concept_memory_instances_do_not_overwrite_each_other(monkeypatch, tmp_path):
    import knowledge.concept_memory as module

    monkeypatch.setattr(module, "PROGRESS_PATH", tmp_path)
    memories = [module.ConceptMemory("shared-book") for _ in range(12)]

    def write(index):
        name = f"??{index}"
        memories[index].log_exposure(
            [{"name": name, "confidence": 1.0}],
            f"???{name}",
        )

    _run_threads([lambda index=index: write(index) for index in range(12)])

    reloaded = module.ConceptMemory("shared-book")
    assert len(reloaded._data["concepts"]) == 12
    assert len(reloaded._data["exposures"]) == 12


def test_study_memory_instances_do_not_lose_chat_messages(monkeypatch, tmp_path):
    import memory.spaced_repetition as sr_module
    import memory.study_memory as module

    monkeypatch.setattr(module, "PROGRESS_PATH", tmp_path)
    monkeypatch.setattr(sr_module, "PROGRESS_PATH", tmp_path)
    memories = [module.StudyMemory("shared-book") for _ in range(12)]

    _run_threads([
        lambda index=index: memories[index].add_chat("user", f"message-{index}", "chapter")
        for index in range(12)
    ])

    history = module.StudyMemory("shared-book").get_chapter_chat("chapter", limit=20)
    assert len(history) == 12
    assert {item["content"] for item in history} == {f"message-{index}" for index in range(12)}


def test_spaced_repetition_instances_do_not_lose_cards(monkeypatch, tmp_path):
    import memory.spaced_repetition as module

    monkeypatch.setattr(module, "PROGRESS_PATH", tmp_path)
    schedulers = [module.SpacedRepetition("shared-book") for _ in range(12)]

    _run_threads([
        lambda index=index: schedulers[index].add_knowledge_point(
            f"chapter::point-{index}", "chapter", f"point-{index}"
        )
        for index in range(12)
    ])

    assert module.SpacedRepetition("shared-book").get_stats()["total"] == 12
