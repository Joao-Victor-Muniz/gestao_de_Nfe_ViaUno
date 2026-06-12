document.addEventListener("DOMContentLoaded", () => {
    carregarCompras();
    
    // Configurar o formulário de upload
    const formUpload = document.getElementById("form-upload-nf");
    formUpload.addEventListener("submit", handleUploadSubmit);

    // Configurar o formulário de nova compra
    const formNovaCompra = document.getElementById("form-nova-compra");
    formNovaCompra.addEventListener("submit", handleNovaCompraSubmit);

    // Configurar o formulário de nova loja
    const formNovaLoja = document.getElementById("form-nova-loja");
    if(formNovaLoja) formNovaLoja.addEventListener("submit", handleNovaLojaSubmit);
    
    const formConfig = document.getElementById("form-config");
    if(formConfig) formConfig.addEventListener("submit", handleConfigSubmit);
    
    const formEmails = document.getElementById("form-enviar-emails");
    if(formEmails) formEmails.addEventListener("submit", handleEnviarEmailsSubmit);
    
    carregarLojas();
});

let todasCompras = [];
let modalUpload;
let modalNovaCompra;
let modalConfig;
let modalEmails;
let ordemInvertida = false;

function carregarCompras() {
    fetch('/api/compras')
        .then(response => response.json())
        .then(data => {
            todasCompras = data;
            aplicarFiltro();
        })
        .catch(error => {
            console.error('Erro ao carregar dados:', error);
            Swal.fire({
                icon: 'error',
                title: 'Erro de Conexão',
                text: 'Não foi possível carregar os dados do servidor local.',
                confirmButtonColor: '#0d6efd'
            });
        });
}

function inverterOrdem() {
    ordemInvertida = !ordemInvertida;
    aplicarFiltro();
}

function aplicarFiltro() {
    const filtro = document.getElementById("filtroStatus").value;
    let comprasFiltradas = [...todasCompras];
    
    if (filtro !== "TODOS") {
        comprasFiltradas = comprasFiltradas.filter(compra => compra.status === filtro);
    }
    
    if (ordemInvertida) {
        comprasFiltradas.reverse();
    }
    
    renderizarTabela(comprasFiltradas);
}

function renderizarTabela(compras) {
    const tbody = document.querySelector("#tabela-compras tbody");
    tbody.innerHTML = '';
    
    if (compras.length === 0) {
        tbody.innerHTML = `<tr><td colspan="9" class="text-center py-4 text-muted">Nenhuma compra registrada no banco de dados.</td></tr>`;
        return;
    }

    compras.forEach(compra => {
        const tr = document.createElement("tr");
        
        // Regra de negócio: Se o "Número da NF" estiver vazio ou o "Status" for "Pendente", a linha fica amarela.
        const pendente = !compra.numero_nf || compra.status === 'Pendente';
        if (pendente) {
            tr.classList.add("linha-pendente");
        }
        
        const formatarData = (dataStr) => {
            if(!dataStr) return '-';
            const d = new Date(dataStr);
            d.setMinutes(d.getMinutes() + d.getTimezoneOffset());
            return d.toLocaleDateString('pt-BR');
        };
        
        const dataRow = formatarData(compra.data_compra);
        const vencRow = formatarData(compra.vencimento);
        const adtoBadge = compra.adto ? '<span class="badge bg-warning text-dark shadow-sm"><i class="fas fa-check-circle me-1"></i>SIM</span>' : '<span class="badge bg-secondary shadow-sm">NÃO</span>';
        const statusBadgeClass = compra.status === 'Concluído' ? 'bg-success' : 'bg-warning text-dark';
        
        tr.innerHTML = `
            <td class="ps-3 fw-bold text-secondary">#${compra.id}</td>
            <td>${dataRow}</td>
            <td class="fw-semibold">${compra.loja}</td>
            <td class="text-success fw-bold">R$ ${compra.valor_compra.toLocaleString('pt-BR', {minimumFractionDigits: 2})}</td>
            <td>${vencRow}</td>
            <td>${compra.centro_custo}</td>
            <td>${adtoBadge}</td>
            <td><span class="badge bg-light text-dark border">${compra.numero_nf || 'Sem NF'}</span></td>
            <td><span class="badge ${statusBadgeClass} shadow-sm">${compra.status}</span></td>
            <td class="text-center pe-3">
                <div class="d-flex justify-content-center gap-2">
                    ${pendente ? `
                        <button class="btn btn-sm btn-primary shadow-sm fw-bold" onclick="abrirModalNf(${compra.id})" title="Adicionar NF">
                            <i class="fas fa-file-upload"></i>
                        </button>
                    ` : `
                        <button class="btn btn-sm btn-light border text-success fw-bold" disabled title="Concluído">
                            <i class="fas fa-check-double"></i>
                        </button>
                    `}
                    <button class="btn btn-sm btn-outline-danger fw-bold shadow-sm" onclick="excluirCompra(${compra.id})" title="Remover Compra">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </td>
        `;
        
        tbody.appendChild(tr);
    });
}

function abrirModalNf(id) {
    document.getElementById("compra_id").value = id;
    document.getElementById("form-upload-nf").reset();
    
    // Setar a data atual como padrão no campo data de recebimento
    document.getElementById("data_recebimento").valueAsDate = new Date();
    
    if(!modalUpload) {
        modalUpload = new bootstrap.Modal(document.getElementById('uploadNfModal'));
    }
    modalUpload.show();
}

function handleUploadSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const id = document.getElementById("compra_id").value;
    const formData = new FormData(form);
    
    // Animação de carregamento no botão
    const btnSubmit = form.querySelector('button[type="submit"]');
    const txtOriginal = btnSubmit.innerHTML;
    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Enviando...';
    btnSubmit.disabled = true;
    
    fetch(`/api/upload_nf/${id}`, {
        method: 'POST',
        body: formData // multipart/form-data automático pelo FormData
    })
    .then(response => response.json().then(data => ({ status: response.status, body: data })))
    .then(result => {
        if (result.status === 200) {
            modalUpload.hide();
            Swal.fire({
                icon: 'success',
                title: 'NF Salva!',
                text: 'A Nota Fiscal foi anexada e enviada por e-mail com sucesso.',
                confirmButtonColor: '#198754'
            });
            carregarCompras(); // Recarregar tabela para remover o fundo amarelo
        } else {
            Swal.fire({
                icon: 'error',
                title: 'Atenção',
                text: result.body.error || 'Erro ao processar a requisição.',
                confirmButtonColor: '#dc3545'
            });
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        Swal.fire({
            icon: 'error',
            title: 'Erro Interno',
            text: 'Ocorreu um erro ao comunicar com o servidor.',
            confirmButtonColor: '#dc3545'
        });
    })
    .finally(() => {
        btnSubmit.innerHTML = txtOriginal;
        btnSubmit.disabled = false;
    });
}

function abrirModalNovaCompra() {
    document.getElementById("form-nova-compra").reset();
    
    if(!modalNovaCompra) {
        modalNovaCompra = new bootstrap.Modal(document.getElementById('novaCompraModal'));
    }
    modalNovaCompra.show();
}

function handleNovaCompraSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const formData = new FormData(form);
    
    // Converter checkbox pra booleano e colocar de volta no FormData
    formData.set('adto', form.querySelector('#adtoSwitch').checked ? 'true' : 'false');
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    const txtOriginal = btnSubmit.innerHTML;
    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Salvando...';
    btnSubmit.disabled = true;
    
    fetch('/api/compras', {
        method: 'POST',
        body: formData // o fetch com FormData já configura o multipart/form-data corretamente
    })
    .then(response => response.json().then(resData => ({ status: response.status, body: resData })))
    .then(result => {
        if (result.status === 201) {
            modalNovaCompra.hide();
            Swal.fire({
                icon: 'success',
                title: 'Compra Adicionada!',
                text: 'A compra foi registrada no sistema.',
                confirmButtonColor: '#198754'
            });
            carregarCompras();
        } else {
            Swal.fire('Erro', result.body.error || 'Erro ao adicionar.', 'error');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        Swal.fire('Erro Interno', 'Falha na comunicação com o servidor.', 'error');
    })
    .finally(() => {
        btnSubmit.innerHTML = txtOriginal;
        btnSubmit.disabled = false;
    });
}

function importarPlanilha(event) {
    const file = event.target.files[0];
    if (!file) return;
    
    const formData = new FormData();
    formData.append('file', file);
    
    Swal.fire({
        title: 'Importando...',
        text: 'Lendo dados da planilha, por favor aguarde.',
        allowOutsideClick: false,
        didOpen: () => {
            Swal.showLoading();
        }
    });
    
    fetch('/api/importar_planilha', {
        method: 'POST',
        body: formData
    })
    .then(response => response.json().then(data => ({ status: response.status, body: data })))
    .then(result => {
        if (result.status === 200) {
            Swal.fire({
                icon: 'success',
                title: 'Importação Concluída!',
                text: result.body.message,
                confirmButtonColor: '#198754'
            });
            carregarCompras();
        } else {
            Swal.fire('Erro na Importação', result.body.error || 'Verifique o formato da planilha.', 'error');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        Swal.fire('Erro Interno', 'Falha ao enviar a planilha para o servidor.', 'error');
    })
    .finally(() => {
        // Resetar o input para permitir enviar o mesmo arquivo novamente se precisar
        event.target.value = '';
    });
}

function excluirCompra(id) {
    Swal.fire({
        title: 'Tem certeza?',
        text: "Essa compra será excluída permanentemente!",
        icon: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#dc3545',
        cancelButtonColor: '#6c757d',
        confirmButtonText: 'Sim, excluir!',
        cancelButtonText: 'Cancelar'
    }).then((result) => {
        if (result.isConfirmed) {
            fetch(`/api/compras/${id}`, {
                method: 'DELETE'
            })
            .then(response => response.json().then(data => ({ status: response.status, body: data })))
            .then(result => {
                if (result.status === 200) {
                    Swal.fire({
                        icon: 'success',
                        title: 'Excluído!',
                        text: 'A compra foi removida.',
                        confirmButtonColor: '#198754'
                    });
                    carregarCompras();
                } else {
                    Swal.fire('Erro', result.body.error || 'Erro ao remover.', 'error');
                }
            })
            .catch(error => {
                console.error('Erro:', error);
                Swal.fire('Erro Interno', 'Falha ao conectar com o servidor.', 'error');
            });
        }
    })
}

let modalNovaLoja;

function carregarLojas() {
    fetch('/api/lojas')
        .then(response => response.json())
        .then(data => {
            const selectLoja = document.getElementById('select-loja');
            if(selectLoja) {
                // Keep the first option
                selectLoja.innerHTML = '<option value="">Selecione uma Loja...</option>';
                data.forEach(loja => {
                    const option = document.createElement('option');
                    option.value = loja.nome;
                    option.textContent = loja.nome;
                    selectLoja.appendChild(option);
                });
            }
        })
        .catch(error => console.error('Erro ao carregar lojas:', error));
}

function abrirModalNovaLoja() {
    document.getElementById("form-nova-loja").reset();
    if(!modalNovaLoja) {
        modalNovaLoja = new bootstrap.Modal(document.getElementById('novaLojaModal'));
    }
    modalNovaLoja.show();
}

function handleNovaLojaSubmit(e) {
    e.preventDefault();
    
    const form = e.target;
    const nomeInput = form.querySelector('#nomeLoja').value;
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    const txtOriginal = btnSubmit.innerHTML;
    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Salvando...';
    btnSubmit.disabled = true;
    
    fetch('/api/lojas', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ nome: nomeInput })
    })
    .then(response => response.json().then(resData => ({ status: response.status, body: resData })))
    .then(result => {
        if (result.status === 201) {
            modalNovaLoja.hide();
            Swal.fire({
                icon: 'success',
                title: 'Loja Cadastrada!',
                text: 'A nova loja foi adicionada.',
                confirmButtonColor: '#198754'
            });
            carregarLojas();
            // Automatically select the new store
            setTimeout(() => {
                const selectLoja = document.getElementById('select-loja');
                if(selectLoja) selectLoja.value = result.body.nome;
            }, 500);
        } else {
            Swal.fire('Erro', result.body.error || 'Erro ao adicionar.', 'error');
        }
    })
    .catch(error => {
        console.error('Erro:', error);
        Swal.fire('Erro Interno', 'Falha na comunicação com o servidor.', 'error');
    })
    .finally(() => {
        btnSubmit.innerHTML = txtOriginal;
        btnSubmit.disabled = false;
    });
}

function abrirModalConfig() {
    fetch('/api/config_email')
        .then(response => response.json())
        .then(data => {
            document.getElementById('smtp_server').value = data.SMTP_SERVER || '';
            document.getElementById('smtp_port').value = data.SMTP_PORT || '';
            document.getElementById('smtp_user').value = data.SMTP_USER || '';
            document.getElementById('smtp_password').value = data.SMTP_PASSWORD || '';
            document.getElementById('envio_automatico').checked = (data.ENVIO_AUTOMATICO === 'true' || data.ENVIO_AUTOMATICO === '1');
            document.getElementById('email_financeiro').value = data.EMAIL_FINANCEIRO || '';
            document.getElementById('email_adiantamentos').value = data.EMAIL_ADIANTAMENTOS || '';
            
            if(!modalConfig) {
                modalConfig = new bootstrap.Modal(document.getElementById('configModal'));
            }
            modalConfig.show();
        });
}

function handleConfigSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    const data = Object.fromEntries(formData.entries());
    
    data.ENVIO_AUTOMATICO = form.querySelector('#envio_automatico').checked ? 'true' : 'false';
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    const txtOriginal = btnSubmit.innerHTML;
    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Salvando...';
    btnSubmit.disabled = true;
    
    fetch('/api/config_email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    })
    .then(r => r.json())
    .then(res => {
        modalConfig.hide();
        Swal.fire('Sucesso!', 'Configurações salvas.', 'success');
    })
    .finally(() => {
        btnSubmit.innerHTML = txtOriginal;
        btnSubmit.disabled = false;
    });
}

function abrirModalEmails() {
    const select = document.getElementById('select-compras-emails');
    select.innerHTML = '';
    
    todasCompras.forEach(compra => {
        const option = document.createElement('option');
        option.value = compra.id;
        const dataStr = new Date(compra.data_compra).toLocaleDateString('pt-BR', {timeZone: 'UTC'});
        option.textContent = `#${compra.id} - ${compra.loja} - ${dataStr} - R$ ${compra.valor_compra} - NF: ${compra.numero_nf || 'Sem NF'}`;
        select.appendChild(option);
    });
    
    document.getElementById("form-enviar-emails").reset();
    
    if(!modalEmails) {
        modalEmails = new bootstrap.Modal(document.getElementById('enviarEmailsModal'));
    }
    modalEmails.show();
}

function handleEnviarEmailsSubmit(e) {
    e.preventDefault();
    const form = e.target;
    const formData = new FormData(form);
    
    const emails = [];
    if(formData.get('email_1')) emails.push(formData.get('email_1'));
    if(formData.get('email_2')) emails.push(formData.get('email_2'));
    if(formData.get('email_3')) emails.push(formData.get('email_3'));
    
    const select = document.getElementById('select-compras-emails');
    const compra_ids = Array.from(select.selectedOptions).map(opt => parseInt(opt.value));
    
    if (emails.length === 0 || compra_ids.length === 0) {
        Swal.fire('Atenção', 'Selecione pelo menos um e-mail e uma compra.', 'warning');
        return;
    }
    
    const btnSubmit = form.querySelector('button[type="submit"]');
    const txtOriginal = btnSubmit.innerHTML;
    btnSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Enviando...';
    btnSubmit.disabled = true;
    
    fetch('/api/enviar_emails_manuais', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ emails, compra_ids })
    })
    .then(r => r.json().then(data => ({status: r.status, body: data})))
    .then(res => {
        if (res.status === 200) {
            modalEmails.hide();
            Swal.fire('Enviado!', res.body.message, 'success');
        } else {
            Swal.fire('Erro', res.body.error, 'error');
        }
    })
    .catch(err => {
        Swal.fire('Erro Interno', 'Falha na comunicação.', 'error');
    })
    .finally(() => {
        btnSubmit.innerHTML = txtOriginal;
        btnSubmit.disabled = false;
    });
}
