import re
from decimal import Decimal, ROUND_HALF_UP
from datetime import date
from collections import defaultdict
from xml.sax.saxutils import escape

import streamlit as st

# =========================================================
# CONFIGURAÇÃO DA PÁGINA
# =========================================================
st.set_page_config(
    page_title="Gerador XML NE001 - SIAFI",
    page_icon="📄",
    layout="wide",
)

# =========================================================
# CSS PERSONALIZADO (VISUAL INSTITUCIONAL)
# =========================================================
st.markdown("""
<style>
html, body, [class*="css"] {
    font-family: "Segoe UI", Arial, sans-serif;
}

h1 {
    color: #003366;
    font-weight: 600;
}

h2, h3 {
    color: #1f4e79;
}

.block-container {
    padding-top: 2rem;
    padding-bottom: 2rem;
}

.stButton > button {
    background-color: #003366;
    color: white;
    font-weight: bold;
    border-radius: 6px;
    padding: 0.6rem 1.5rem;
    width: 100%;
}

.stButton > button:hover {
    background-color: #00509e;
    color: white;
}

textarea {
    font-size: 14px;
}

section[data-testid="stSidebar"] {
    background-color: #f4f6f9;
}
</style>
""", unsafe_allow_html=True)

# =========================================================
# CONSTANTES
# =========================================================
ANO_REFERENCIA = "2026"
IDENTIFICADOR_ORIGEM = "SIAFI-STN"
COD_FAVORECIDO_PADRAO = "120052"

AMPARO_LEGAL_OPCOES = {
    "104 - Modalidade Não Se Aplica": "104",
    "001 - Concorrência": "001",
    "002 - Tomada de Preços": "002",
    "003 - Convite": "003",
    "004 - Concurso": "004",
    "005 - Leilão": "005",
    "006 - Pregão": "006",
    "007 - Diálogo Competitivo": "007",
    "008 - Dispensa de Licitação": "008",
    "009 - Inexigibilidade": "009",
}

TIPO_EMPENHO_OPCOES = {
    "1 - Empenho Ordinário": "1",
    "3 - Empenho Estimativo": "3",
    "5 - Empenho Global": "5",
}

# =========================================================
# FUNÇÕES AUXILIARES
# =========================================================
def parse_brl_number(s: str) -> Decimal:
    s = s.strip().replace(".", "").replace(",", ".")
    return Decimal(s)

def fmt_money(d: Decimal) -> str:
    return format(d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")

def normalize_cpf(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")

def parse_lines(data_text: str):
    rows = []
    for line in (data_text or "").strip().splitlines():
        parts = re.split(r"\s+", line.strip())
        if len(parts) != 7:
            raise ValueError(f"Linha inválida (esperado 7 colunas): {line}")

        esfera, ptres, ndd, fonte, ugr, pi, valor = parts

        if not re.fullmatch(r"\d{6}", ptres):
            raise ValueError(f"PTRES inválido: {ptres}")

        ndd_digits = re.sub(r"\D", "", ndd)
        cod_nat_desp = ndd_digits[:6]
        cod_sub_elemento = ndd_digits[-2:]

        if not fonte.strip():
            raise ValueError("Fonte não pode ser vazia.")

        rows.append({
            "esfera": esfera,
            "ptres": ptres,
            "codNatDesp": cod_nat_desp,
            "codSubElemento": cod_sub_elemento,
            "codFonteRec": fonte,
            "ugResponsavel": ugr,
            "codPlanoInterno": pi,
            "valor": parse_brl_number(valor),
        })

    if not rows:
        raise ValueError("Informe ao menos uma linha de dados.")

    return rows

# =========================================================
# FUNÇÃO PRINCIPAL DE GERAÇÃO DO XML
# =========================================================
def build_xml(
    data_text,
    cpf,
    ug_executora,
    observacao,
    descricao_item,
    data_evento,
    nup,
    tipo_empenho,
    cod_amparo_legal,
    ptres_passivo,
    conta_passivo,
):
    cpf_digits = normalize_cpf(cpf)
    if len(cpf_digits) != 11:
        raise ValueError("CPF deve conter 11 dígitos.")

    if not re.fullmatch(r"\d{6}", ug_executora):
        raise ValueError("UG Executora deve conter 6 dígitos.")

    rows = parse_lines(data_text)

    groups = defaultdict(list)
    for r in rows:
        key = (
            r["esfera"],
            r["ptres"],
            r["codNatDesp"],
            r["codFonteRec"],
            r["ugResponsavel"],
            r["codPlanoInterno"],
        )
        groups[key].append(r)

    detalhes = []

    for key in sorted(groups.keys()):
        esfera, ptres, codNatDesp, codFonteRec, ugResp, pi = key
        items = groups[key]
        total = sum((i["valor"] for i in items), Decimal("0"))

        passivo_block = ""
        if ptres in ptres_passivo or codNatDesp.startswith(("3192", "3392")):
            passivo_block = f"""
        <passivoAnterior>
          <codContaContabil>{conta_passivo}</codContaContabil>
        </passivoAnterior>
"""

        itens_xml = []
        for idx, it in enumerate(items, start=1):
            val = fmt_money(it["valor"])
            desc = f"{descricao_item} - ND {codNatDesp} SE {it['codSubElemento']}"
            itens_xml.append(f"""
        <itemEmpenho>
          <numSeqItem>{idx}</numSeqItem>
          <codSubElemento>{it['codSubElemento']}</codSubElemento>
          <descricao>{escape(desc)}</descricao>
          <operacaoItemEmpenho>
            <tipoOperacaoItemEmpenho>INCLUSAO</tipoOperacaoItemEmpenho>
            <quantidade>1</quantidade>
            <vlrUnitario>{val}</vlrUnitario>
            <vlrOperacao>{val}</vlrOperacao>
          </operacaoItemEmpenho>
        </itemEmpenho>
""")

        detalhes.append(f"""
    <sb:detalhe>
      <ns2:orcEmpenhoDados>
        <ugEmitente>{ug_executora}</ugEmitente>
        <anoEmpenho>{ANO_REFERENCIA}</anoEmpenho>
        <tipoEmpenho>{tipo_empenho}</tipoEmpenho>
        <celulaOrcamentaria>
          <esfera>{esfera}</esfera>
          <codPTRES>{ptres}</codPTRES>
          <codFonteRec>{codFonteRec}</codFonteRec>
          <codNatDesp>{codNatDesp}</codNatDesp>
          <ugResponsavel>{ugResp}</ugResponsavel>
          <codPlanoInterno>{escape(pi)}</codPlanoInterno>
        </celulaOrcamentaria>
        <dtEmis>{data_evento.strftime("%Y-%m-%d")}</dtEmis>
        <txtProcesso>{escape(nup)}</txtProcesso>
        <vlrEmpenho>{fmt_money(total)}</vlrEmpenho>
        <codFavorecido>{COD_FAVORECIDO_PADRAO}</codFavorecido>
        <codAmparoLegal>{cod_amparo_legal}</codAmparoLegal>
        <txtDescricao>{escape(observacao)}</txtDescricao>
        {passivo_block}
        {''.join(itens_xml)}
      </ns2:orcEmpenhoDados>
    </sb:detalhe>
""")

    return f"""<sb:arquivo xmlns:ns2="http://services.orcamentario.siafi.tesouro.fazenda.gov.br/"
xmlns:sb="http://www.tesouro.gov.br/siafi/submissao">
  <sb:header>
    <sb:codigoLayout>NE001</sb:codigoLayout>
    <sb:dataGeracao>{data_evento.strftime("%d/%m/%Y")}</sb:dataGeracao>
    <sb:sequencialGeracao>1</sb:sequencialGeracao>
    <sb:anoReferencia>{ANO_REFERENCIA}</sb:anoReferencia>
    <sb:ugResponsavel>{ug_executora}</sb:ugResponsavel>
    <sb:cpfResponsavel>{cpf_digits}</sb:cpfResponsavel>
    <sb:identificadorOrigem>{IDENTIFICADOR_ORIGEM}</sb:identificadorOrigem>
  </sb:header>
  <sb:detalhes>
    {''.join(detalhes)}
  </sb:detalhes>
  <sb:trailler>
    <sb:quantidadeDetalhe>{len(detalhes)}</sb:quantidadeDetalhe>
  </sb:trailler>
</sb:arquivo>
"""

# =========================================================
# INTERFACE
# =========================================================
st.markdown("<h1 style='text-align:center;'>Gerador de Empenho XML</h1>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns(4)
cpf = col1.text_input("CPF do responsável")
ug_executora = col2.text_input("UG Executora (6 dígitos)")
data_evento = col3.date_input("Data do empenho", value=date.today())
nup = col4.text_input("NUP / Processo")

st.divider()
observacao = st.text_input("Descrição geral do empenho")
descricao_item = st.text_input("Descrição dos itens")

st.divider()
data_text = st.text_area(
    "Dados (esfera PTRES NDD fonte UGR PI valor)",
    height=280,
)

with st.sidebar:
    st.markdown("## ⚙️ Configurações")

    tipo_label = st.selectbox("Tipo de Empenho", list(TIPO_EMPENHO_OPCOES.keys()))
    tipo_empenho = TIPO_EMPENHO_OPCOES[tipo_label]

    amparo_label = st.selectbox("Modalidade / Amparo Legal", list(AMPARO_LEGAL_OPCOES.keys()))
    cod_amparo_legal = AMPARO_LEGAL_OPCOES[amparo_label]

    st.markdown("### 💼 Passivo Anterior")
    st.info(
        "Além dos PTRES selecionados, toda Natureza de Despesa de exercício anterior "
        "(ND iniciada por 3192 ou 3392) também gera a tag de passivo anterior."
    )

    conta_passivo = st.text_input(
        "Conta Contábil do Passivo",
        value="211110101"
    )

    ptres_passivo = set(
        st.multiselect(
            "PTRES",
            default=["168870", "249586", "137835"],
            options=["168870", "249586", "137835"],
        )
    )

    extras = st.text_input("Outros PTRES (vírgula)")
    if extras.strip():
        for p in extras.split(","):
            p = p.strip()
            if re.fullmatch(r"\d{6}", p):
                ptres_passivo.add(p)

st.divider()

if st.button("Gerar XML NE001"):
    try:
        xml = build_xml(
            data_text,
            cpf,
            ug_executora,
            observacao,
            descricao_item,
            data_evento,
            nup,
            tipo_empenho,
            cod_amparo_legal,
            ptres_passivo,
            conta_passivo,
        )
        st.success("XML gerado com sucesso!")
        st.download_button("📥 Baixar XML", xml.encode("utf-8"), "NE001.xml", "application/xml")
    except Exception as e:
        st.error(str(e))