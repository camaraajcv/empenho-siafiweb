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
    page_title="Geração de Empenhos - SDPP Via XML",
    page_icon="📄",
    layout="wide",
)

# =========================================================
# CSS PERSONALIZADO (VISUAL INSTITUCIONAL)
# =========================================================
st.markdown("""
<style>
.block-container { max-width: 1350px; padding-top: 2.4rem; padding-bottom: 3rem; }
.sdpp-hero {
    background: linear-gradient(120deg, #102b46, #174e6b);
    border-radius: 18px; padding: 2.1rem 2.4rem; color: #fff;
    margin-bottom: 1.6rem; box-shadow: 0 12px 32px rgba(16,43,70,.12);
}
.sdpp-eyebrow {
    color: #a9d8df; font-size: .76rem; font-weight: 700;
    letter-spacing: .16em; text-transform: uppercase; margin-bottom: .8rem;
}
.sdpp-hero h1 {
    color: #fff; font-size: clamp(1.6rem, 3vw, 2.35rem); font-weight: 700;
    line-height: 1.2; padding: 0; margin: 0 0 .85rem;
}
.sdpp-hero p { color: #d7e6ee; font-size: .98rem; margin: 0; max-width: 780px; }
.sdpp-badges { display: flex; flex-wrap: wrap; gap: .5rem; margin-top: 1.3rem; }
.sdpp-badges span {
    border: 1px solid rgba(255,255,255,.23); border-radius: 20px;
    padding: .3rem .75rem; color: #e4f1f5; font-size: .78rem;
}
.sdpp-section { margin: .25rem 0 1.2rem; }
.sdpp-section h2 { font-size: 1.25rem; font-weight: 650; padding: 0; margin: 0 0 .35rem; }
.sdpp-section p { font-size: .92rem; opacity: .75; margin: 0; }
div[data-testid="stVerticalBlockBorderWrapper"] > div { border-radius: 12px; }
div[data-testid="stTextInput"] input,
div[data-testid="stTextArea"] textarea { border-radius: 8px; }
div[data-testid="stTextArea"] textarea {
    font-family: ui-monospace, SFMono-Regular, Consolas, monospace;
    font-size: .88rem; line-height: 1.6;
}
div[data-testid="stButton"] button,
div[data-testid="stDownloadButton"] button {
    background: #174e6b; color: #fff; border: 1px solid #174e6b;
    font-weight: 650; border-radius: 9px; padding: .7rem 1.4rem;
}
div[data-testid="stButton"] button:hover,
div[data-testid="stDownloadButton"] button:hover {
    background: #102b46; color: #fff; border-color: #102b46;
}
div[data-testid="stButton"] button { width: 100%; }
div[data-testid="stMetric"] {
    background: rgba(128,145,160,.07); border: 1px solid rgba(128,145,160,.20);
    border-radius: 12px; padding: 1rem 1.15rem;
}
div[data-testid="stMetricValue"] { font-size: clamp(1.25rem, 2vw, 1.8rem); }
section[data-testid="stSidebar"] { border-right: 1px solid rgba(128,145,160,.2); }
section[data-testid="stSidebar"] h2 { font-size: 1.2rem; }
section[data-testid="stSidebar"] h3 { font-size: 1.02rem; }
.sdpp-footer {
    margin-top: 2rem; padding-top: 1rem; border-top: 1px solid rgba(128,145,160,.22);
    font-size: .8rem; opacity: .65;
}
@media (max-width: 700px) {
    .block-container { padding-top: 1.3rem; }
    .sdpp-hero { padding: 1.5rem; border-radius: 12px; }
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

# Conta de passivo anterior por Natureza de Despesa e subelemento.
CONTAS_PASSIVO_ANTERIOR = {
    ("319092", "94"): "218910100",
    ("339092", "59"): "211210100",
    ("339092", "08"): "211310100",
    ("339092", "93"): "211310100",
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
        conta_passivo_grupo = CONTAS_PASSIVO_ANTERIOR.get(
            (r["codNatDesp"], r["codSubElemento"])
        )
        if conta_passivo_grupo is None and (
            r["ptres"] in ptres_passivo
            or r["codNatDesp"] in {"319092", "339092"}
        ):
            conta_passivo_grupo = conta_passivo

        # A tag pertence ao empenho: contas diferentes exigem grupos separados.
        key = (
            r["esfera"],
            r["ptres"],
            r["codNatDesp"],
            r["codFonteRec"],
            r["ugResponsavel"],
            r["codPlanoInterno"],
            conta_passivo_grupo,
        )
        groups[key].append(r)

    detalhes = []

    for key in sorted(groups.keys()):
        esfera, ptres, codNatDesp, codFonteRec, ugResp, pi, conta_passivo_grupo = key
        items = groups[key]
        total = sum((i["valor"] for i in items), Decimal("0"))

        passivo_block = ""
        if conta_passivo_grupo is not None:
            passivo_block = f"""
        <passivoAnterior>
          <codContaContabil>{conta_passivo_grupo}</codContaContabil>
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
st.markdown("""
<div class="sdpp-hero">
    <div class="sdpp-eyebrow">SDPP &nbsp; / &nbsp; Execução orçamentária</div>
    <h1>Geração de Empenhos - SDPP Via XML</h1>
    <p>Prepare os dados da folha de pagamento e gere o arquivo de empenhos
    para importação no SIAFI.</p>
    <div class="sdpp-badges">
        <span>Leiaute NE001</span>
        <span>Exercício """ + ANO_REFERENCIA + """</span>
        <span>Passivo anterior automático</span>
    </div>
</div>
""", unsafe_allow_html=True)

with st.container(border=True):
    st.markdown("""
    <div class="sdpp-section">
        <h2>01 · Identificação do empenho</h2>
        <p>Informe o responsável, a unidade executora e os dados do processo.</p>
    </div>
    """, unsafe_allow_html=True)
    col1, col2 = st.columns(2)
    cpf = col1.text_input("CPF do responsável")
    ug_executora = col2.text_input("UG Executora (6 dígitos)")
    col3, col4 = st.columns(2)
    data_evento = col3.date_input("Data do empenho", value=date.today())
    nup = col4.text_input("NUP / Processo")

with st.container(border=True):
    st.markdown("""
    <div class="sdpp-section">
        <h2>02 · Descrição da despesa</h2>
        <p>Defina os textos que identificarão o empenho e seus itens.</p>
    </div>
    """, unsafe_allow_html=True)
    observacao = st.text_input("Descrição geral do empenho")
    descricao_item = st.text_input("Descrição dos itens")

with st.container(border=True):
    st.markdown("""
    <div class="sdpp-section">
        <h2>03 · Dados orçamentários</h2>
        <p>Cole as linhas da planilha, mantendo a ordem das sete colunas.</p>
    </div>
    """, unsafe_allow_html=True)
    st.caption("Esfera · PTRES · NDD (ND + subelemento) · Fonte · UGR · PI · Valor")
    data_text = st.text_area(
        "Dados (esfera PTRES NDD fonte UGR PI valor)",
        height=280,
        placeholder="1 168870 31909294 1000000000 120052 PLANO_INTERNO 1.000,00",
    )
    st.caption("Use valores no padrão brasileiro, como 1.000,00. "
               "Confira o tipo de empenho, o amparo legal e o passivo anterior no painel lateral.")

with st.sidebar:
    st.markdown("## Parâmetros do empenho")
    st.caption("Defina as opções aplicadas ao arquivo XML.")

    tipo_label = st.selectbox("Tipo de Empenho", list(TIPO_EMPENHO_OPCOES.keys()))
    tipo_empenho = TIPO_EMPENHO_OPCOES[tipo_label]

    amparo_label = st.selectbox("Modalidade / Amparo Legal", list(AMPARO_LEGAL_OPCOES.keys()))
    cod_amparo_legal = AMPARO_LEGAL_OPCOES[amparo_label]

    st.divider()
    st.markdown("### Passivo anterior")
    st.caption("As NDs 319092 e 339092 e os PTRES selecionados geram a tag de passivo anterior.")
    with st.expander("Consultar contas automáticas"):
        st.markdown(
            "| ND / subelemento | Conta contábil |\n"
            "|---|---|\n"
            "| 319092 / 94 | 218910100 |\n"
            "| 339092 / 59 | 211210100 |\n"
            "| 339092 / 08 e 93 | 211310100 |"
        )
        st.caption("Para as demais combinações, será usada a conta informada abaixo.")


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
st.markdown("#### Gerar arquivo de empenhos")
st.caption("O arquivo será disponibilizado após a validação dos dados informados.")

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
        st.success("Arquivo de empenhos gerado com sucesso.")
        resumo = st.columns(3)
        linhas = parse_lines(data_text)
        resumo[0].metric("Itens informados", len(linhas))
        resumo[1].metric("Empenhos no arquivo", xml.count("<sb:detalhe>"))
        total = sum((linha["valor"] for linha in linhas), Decimal("0"))
        total_br = f"{total:,.2f}".translate(str.maketrans({",": ".", ".": ","}))
        resumo[2].metric("Valor total", total_br)
        st.download_button("Baixar XML de empenhos · NE001", xml.encode("utf-8"), "NE001.xml", "application/xml")
    except Exception as e:
        st.error(str(e))

st.markdown('<div class="sdpp-footer">SDPP · Geração de empenhos · Integração SIAFI / NE001</div>', unsafe_allow_html=True)
