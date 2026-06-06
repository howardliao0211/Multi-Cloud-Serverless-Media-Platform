SPECIES_CLASSES = [
    "Alectura_lathami", "Antechinus_agilis", "Bos_taurus",
    "Burhinus_grallarius", "Canis_familiaris",
    "Chalcophaps_longirostris", "Colluricincla_harmonica",
    "Corcorax_melanorhamphos", "Dacelo_novaeguineae",
    "Dama_dama", "Eopsaltria_australis", "Felis_catus",
    "Geopelia_humeralis", "Gymnorhina_tibicen", "Homo_sapiens",
    "Isoodon_macrourus", "Lepus_europaeus", "Macropus_giganteus",
    "Menura_novaehollandiae", "Mus_musculus",
    "Oryctolagus_cuniculus", "Perameles_nasuta", "Pitta_versicolor",
    "Rattus", "Rattus_fuscipes", "Rattus_rattus",
    "Strepera_graculina", "Sus_scrofa", "Tachyglossus_aculeatus",
    "Thylogale_stigmatica", "Trichosurus_caninus",
    "Trichosurus_cunninghami", "Trichosurus_vulpecula",
    "Varanus_varius", "Vombatus_ursinus", "Vulpes_vulpes",
    "Wallabia_bicolor", "Canis_dingo", "Capra_hircus",
    "Casuarius_casuarius", "Heteromyias_cinereifrons",
    "Hypsiprymnodon_moschatus", "Megapodius_reinwardt",
    "Notamacropus_rufogriseus", "Orthonyx_spaldingii",
    "Uromys_caudimaculatus",
]

NORMALIZED_SPECIES_BY_LOWER = {
    species.lower(): species
    for species in SPECIES_CLASSES
}


def normalize_species_tag(tag: str) -> str | None:
    return NORMALIZED_SPECIES_BY_LOWER.get(tag.strip().lower())
