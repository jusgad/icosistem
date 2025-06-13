/**
 * TableManager Component
 * Componente avanzado para la gestión y visualización de tablas de datos
 * Soporta paginación, ordenamiento, filtrado, exportación y personalización
 * @author Ecosistema Emprendimiento
 * @version 1.0.0
 */

class EcoTableManager {
    constructor(element, options = {}) {
        this.element = typeof element === 'string' ? document.getElementById(element) : element;
        if (!this.element) {
            throw new Error('TableManager element not found');
        }

        this.config = {
            // Datos y Columnas
            data: options.data || [], // Puede ser un array de objetos o una URL
            columns: options.columns || [], // Definición de columnas: { key: 'id', label: 'ID', sortable: true, filterable: true, render: (value, row) => value }
            
            // Paginación
            pagination: options.pagination !== false,
            pageSize: options.pageSize || 10,
            pageSizeOptions: options.pageSizeOptions || [10, 25, 50, 100],
            
            // Ordenamiento
            sorting: options.sorting !== false,
            defaultSortColumn: options.defaultSortColumn || null,
            defaultSortOrder: options.defaultSortOrder || 'asc', // asc, desc
            
            // Filtrado y Búsqueda
            filtering: options.filtering !== false,
            searchPlaceholder: options.searchPlaceholder || 'Buscar en la tabla...',
            
            // Selección de Filas
            selectable: options.selectable || false, // false, 'single', 'multiple'
            
            // Acciones
            rowActions: options.rowActions || [], // [{ label: 'Editar', icon: 'fa-edit', handler: (row) => {} }]
            bulkActions: options.bulkActions || [], // [{ label: 'Eliminar Seleccionados', handler: (selectedRows) => {} }]
            
            // Exportación
            exportable: options.exportable !== false,
            exportFormats: options.exportFormats || ['csv', 'json', 'excel'],
            
            // Apariencia y UI
            theme: options.theme || 'light', // light, dark
            responsive: options.responsive !== false,
            showRowNumbers: options.showRowNumbers || false,
            emptyTableMessage: options.emptyTableMessage || 'No hay datos disponibles',
            loadingMessage: options.loadingMessage || 'Cargando datos...',
            
            // Server-side
            serverSide: options.serverSide || false,
            dataUrl: options.dataUrl || null, // URL para cargar datos si serverSide es true
            
            // Callbacks
            onRowClick: options.onRowClick || null,
            onSort: options.onSort || null,
            onFilter: options.onFilter || null,
            onPageChange: options.onPageChange || null,
            onSelectionChange: options.onSelectionChange || null,
            
            // Contexto del ecosistema
            ecosystemContext: options.ecosystemContext || 'general_table', // projects_table, users_table
            
            ...options
        };

        this.state = {
            currentPage: 1,
            currentSortColumn: this.config.defaultSortColumn,
            currentSortOrder: this.config.defaultSortOrder,
            currentFilter: '',
            selectedRows: new Set(),
            data: [],
            totalRows: 0,
            isLoading: false,
            tableElement: null,
            paginationElement: null,
            filterElement: null
        };

        this.eventListeners = [];
        this.init();
    }

    /**
     * Inicialización del componente
     */
    async init() {
        try {
            this.element.innerHTML = ''; // Limpiar contenido previo
            this.createTableStructure();
            
            if (this.config.serverSide && this.config.dataUrl) {
                await this.fetchData();
            } else {
                this.state.data = Array.isArray(this.config.data) ? this.config.data : [];
                this.state.totalRows = this.state.data.length;
                this.render();
            }
            
            this.setupEventListeners();
            console.log('📊 EcoTableManager initialized successfully');
        } catch (error) {
            console.error('❌ Error initializing EcoTableManager:', error);
            this.handleError(error);
        }
    }

    /**
     * Crear estructura HTML de la tabla
     */
    createTableStructure() {
        const wrapper = document.createElement('div');
        wrapper.className = `eco-table-manager theme-${this.config.theme} ${this.config.responsive ? 'responsive' : ''}`;

        // Controles superiores (filtro, acciones masivas)
        if (this.config.filtering || this.config.bulkActions.length > 0) {
            const topControls = document.createElement('div');
            topControls.className = 'table-controls-top';
            if (this.config.filtering) {
                topControls.innerHTML += `
                    <div class="table-filter">
                        <input type="text" class="form-control filter-input" placeholder="${this.config.searchPlaceholder}">
                    </div>
                `;
            }
            // TODO: Añadir bulk actions
            wrapper.appendChild(topControls);
        }

        // Tabla
        this.state.tableElement = document.createElement('table');
        this.state.tableElement.className = 'table table-striped table-hover'; // Clases de Bootstrap
        wrapper.appendChild(this.state.tableElement);

        // Paginación
        if (this.config.pagination) {
            this.state.paginationElement = document.createElement('div');
            this.state.paginationElement.className = 'table-pagination';
            wrapper.appendChild(this.state.paginationElement);
        }
        
        this.element.appendChild(wrapper);
        this.state.filterElement = wrapper.querySelector('.filter-input');
    }

    /**
     * Renderizar la tabla completa (header, body, footer, paginación)
     */
    render() {
        if (!this.state.tableElement) return;
        this.state.isLoading = true;
        this.showLoading();

        this.renderTableHeader();
        this.renderTableBody();
        // this.renderTableFooter(); // Opcional
        if (this.config.pagination) {
            this.renderPagination();
        }
        
        this.state.isLoading = false;
        this.hideLoading();
    }

    /**
     * Renderizar encabezado de la tabla
     */
    renderTableHeader() {
        let thead = this.state.tableElement.querySelector('thead');
        if (!thead) {
            thead = document.createElement('thead');
            this.state.tableElement.appendChild(thead);
        }
        thead.innerHTML = '';
        const tr = document.createElement('tr');

        if (this.config.selectable === 'multiple') {
            const thCheckbox = document.createElement('th');
            thCheckbox.innerHTML = '<input type="checkbox" class="select-all-rows">';
            tr.appendChild(thCheckbox);
        } else if (this.config.selectable === 'single') {
             tr.appendChild(document.createElement('th')); // Espacio para radio
        }

        if (this.config.showRowNumbers) {
            tr.appendChild(document.createElement('th')).textContent = '#';
        }

        this.config.columns.forEach(col => {
            const th = document.createElement('th');
            th.textContent = col.label;
            th.dataset.key = col.key;
            if (col.sortable && this.config.sorting) {
                th.classList.add('sortable');
                if (this.state.currentSortColumn === col.key) {
                    th.classList.add(this.state.currentSortOrder === 'asc' ? 'sorted-asc' : 'sorted-desc');
                }
            }
            tr.appendChild(th);
        });

        if (this.config.rowActions.length > 0) {
            tr.appendChild(document.createElement('th')).textContent = 'Acciones';
        }
        thead.appendChild(tr);
    }

    /**
     * Renderizar cuerpo de la tabla
     */
    renderTableBody() {
        let tbody = this.state.tableElement.querySelector('tbody');
        if (!tbody) {
            tbody = document.createElement('tbody');
            this.state.tableElement.appendChild(tbody);
        }
        tbody.innerHTML = '';

        const dataToRender = this.getPaginatedData();

        if (dataToRender.length === 0) {
            const trEmpty = document.createElement('tr');
            const tdEmpty = document.createElement('td');
            tdEmpty.colSpan = this.config.columns.length + 
                              (this.config.selectable ? 1 : 0) + 
                              (this.config.showRowNumbers ? 1 : 0) +
                              (this.config.rowActions.length > 0 ? 1 : 0);
            tdEmpty.textContent = this.config.emptyTableMessage;
            tdEmpty.className = 'text-center';
            trEmpty.appendChild(tdEmpty);
            tbody.appendChild(trEmpty);
            return;
        }

        dataToRender.forEach((row, index) => {
            const tr = document.createElement('tr');
            tr.dataset.rowIndex = this.config.pagination ? (this.state.currentPage - 1) * this.config.pageSize + index : index;

            if (this.config.selectable === 'multiple') {
                const tdCheckbox = document.createElement('td');
                const checkbox = document.createElement('input');
                checkbox.type = 'checkbox';
                checkbox.className = 'row-selector';
                checkbox.checked = this.state.selectedRows.has(row[this.getPrimaryKey()]);
                checkbox.dataset.rowId = row[this.getPrimaryKey()];
                tdCheckbox.appendChild(checkbox);
                tr.appendChild(tdCheckbox);
            } else if (this.config.selectable === 'single') {
                // Implementar radio buttons si es necesario
            }

            if (this.config.showRowNumbers) {
                const tdNum = document.createElement('td');
                tdNum.textContent = (this.state.currentPage - 1) * this.config.pageSize + index + 1;
                tr.appendChild(tdNum);
            }

            this.config.columns.forEach(col => {
                const td = document.createElement('td');
                const value = this.getNestedValue(row, col.key);
                td.innerHTML = col.render ? col.render(value, row) : (value !== null && value !== undefined ? value : '');
                tr.appendChild(td);
            });

            if (this.config.rowActions.length > 0) {
                const tdActions = document.createElement('td');
                this.config.rowActions.forEach(action => {
                    const btn = document.createElement('button');
                    btn.className = 'btn btn-sm btn-outline-secondary me-1';
                    btn.innerHTML = action.icon ? `<i class="fa ${action.icon}"></i>` : action.label;
                    btn.title = action.label;
                    btn.addEventListener('click', (e) => {
                        e.stopPropagation();
                        action.handler(row);
                    });
                    tdActions.appendChild(btn);
                });
                tr.appendChild(tdActions);
            }
            tbody.appendChild(tr);
        });
    }

    /**
     * Renderizar paginación
     */
    renderPagination() {
        if (!this.state.paginationElement) return;
        this.state.paginationElement.innerHTML = '';

        const totalPages = Math.ceil(this.state.totalRows / this.config.pageSize);
        if (totalPages <= 1) return;

        const ul = document.createElement('ul');
        ul.className = 'pagination justify-content-center'; // Clases de Bootstrap

        // Botón "Anterior"
        const prevLi = document.createElement('li');
        prevLi.className = `page-item ${this.state.currentPage === 1 ? 'disabled' : ''}`;
        prevLi.innerHTML = `<a class="page-link" href="#" data-page="${this.state.currentPage - 1}">Anterior</a>`;
        ul.appendChild(prevLi);

        // Números de página (simplificado)
        // Idealmente, implementar lógica para mostrar "..." para muchas páginas
        for (let i = 1; i <= totalPages; i++) {
            const pageLi = document.createElement('li');
            pageLi.className = `page-item ${this.state.currentPage === i ? 'active' : ''}`;
            pageLi.innerHTML = `<a class="page-link" href="#" data-page="${i}">${i}</a>`;
            ul.appendChild(pageLi);
        }

        // Botón "Siguiente"
        const nextLi = document.createElement('li');
        nextLi.className = `page-item ${this.state.currentPage === totalPages ? 'disabled' : ''}`;
        nextLi.innerHTML = `<a class="page-link" href="#" data-page="${this.state.currentPage + 1}">Siguiente</a>`;
        ul.appendChild(nextLi);
        
        this.state.paginationElement.appendChild(ul);
    }

    /**
     * Obtener datos paginados y filtrados/ordenados
     */
    getPaginatedData() {
        let data = [...this.state.data];

        // Filtrado
        if (this.config.filtering && this.state.currentFilter) {
            const filterText = this.state.currentFilter.toLowerCase();
            data = data.filter(row => 
                this.config.columns.some(col => {
                    if (col.filterable !== false) {
                        const value = this.getNestedValue(row, col.key);
                        return String(value).toLowerCase().includes(filterText);
                    }
                    return false;
                })
            );
        }

        // Ordenamiento
        if (this.config.sorting && this.state.currentSortColumn) {
            data.sort((a, b) => {
                const valA = this.getNestedValue(a, this.state.currentSortColumn);
                const valB = this.getNestedValue(b, this.state.currentSortColumn);
                
                if (valA < valB) return this.state.currentSortOrder === 'asc' ? -1 : 1;
                if (valA > valB) return this.state.currentSortOrder === 'asc' ? 1 : -1;
                return 0;
            });
        }
        
        // Actualizar total de filas después de filtrar (para paginación correcta)
        if (!this.config.serverSide) {
            this.state.totalRows = data.length;
        }

        // Paginación
        if (this.config.pagination && !this.config.serverSide) {
            const start = (this.state.currentPage - 1) * this.config.pageSize;
            const end = start + this.config.pageSize;
            return data.slice(start, end);
        }
        
        return data;
    }

    /**
     * Configurar event listeners
     */
    setupEventListeners() {
        // Ordenamiento
        if (this.config.sorting) {
            this.state.tableElement.querySelector('thead').addEventListener('click', (e) => {
                const th = e.target.closest('th.sortable');
                if (th) {
                    this.handleSort(th.dataset.key);
                }
            });
        }

        // Paginación
        if (this.config.pagination) {
            this.state.paginationElement.addEventListener('click', (e) => {
                e.preventDefault();
                const pageLink = e.target.closest('a[data-page]');
                if (pageLink && !e.target.closest('.disabled')) {
                    this.handlePageChange(parseInt(pageLink.dataset.page));
                }
            });
        }
        
        // Filtro
        if (this.config.filtering && this.state.filterElement) {
            this.state.filterElement.addEventListener('input', this.debounce((e) => {
                this.handleFilter(e.target.value);
            }, 300));
        }
        
        // Selección de filas
        if (this.config.selectable) {
            this.state.tableElement.addEventListener('change', (e) => {
                if (e.target.matches('.row-selector')) {
                    this.handleRowSelection(e.target.dataset.rowId, e.target.checked);
                } else if (e.target.matches('.select-all-rows')) {
                    this.handleSelectAll(e.target.checked);
                }
            });
        }
        
        // Click en fila
        if (this.config.onRowClick) {
            this.state.tableElement.addEventListener('click', (e) => {
                const tr = e.target.closest('tr');
                if (tr && tr.parentElement.tagName === 'TBODY') {
                    const rowIndex = parseInt(tr.dataset.rowIndex);
                    const rowData = this.getPaginatedData()[rowIndex - ((this.state.currentPage - 1) * this.config.pageSize)];
                    if (rowData) {
                        this.config.onRowClick(rowData, tr, e);
                    }
                }
            });
        }
    }

    /**
     * Manejar ordenamiento
     */
    handleSort(columnKey) {
        if (this.state.currentSortColumn === columnKey) {
            this.state.currentSortOrder = this.state.currentSortOrder === 'asc' ? 'desc' : 'asc';
        } else {
            this.state.currentSortColumn = columnKey;
            this.state.currentSortOrder = 'asc';
        }
        
        if (this.config.serverSide) {
            this.fetchData();
        } else {
            this.render();
        }
        
        if (this.config.onSort) {
            this.config.onSort(this.state.currentSortColumn, this.state.currentSortOrder);
        }
    }

    /**
     * Manejar cambio de página
     */
    handlePageChange(pageNumber) {
        this.state.currentPage = pageNumber;
        if (this.config.serverSide) {
            this.fetchData();
        } else {
            this.render(); // Solo re-renderizar cuerpo y paginación
        }
        if (this.config.onPageChange) {
            this.config.onPageChange(pageNumber);
        }
    }
    
    /**
     * Manejar filtro
     */
    handleFilter(filterText) {
        this.state.currentFilter = filterText;
        this.state.currentPage = 1; // Resetear a primera página
        if (this.config.serverSide) {
            this.fetchData();
        } else {
            this.render();
        }
        if (this.config.onFilter) {
            this.config.onFilter(filterText);
        }
    }
    
    /**
     * Manejar selección de fila
     */
    handleRowSelection(rowId, isSelected) {
        if (this.config.selectable === 'single') {
            this.state.selectedRows.clear();
            if (isSelected) {
                this.state.selectedRows.add(rowId);
            }
        } else if (this.config.selectable === 'multiple') {
            if (isSelected) {
                this.state.selectedRows.add(rowId);
            } else {
                this.state.selectedRows.delete(rowId);
            }
        }
        
        // Actualizar UI de selección
        this.updateSelectionUI();
        
        if (this.config.onSelectionChange) {
            this.config.onSelectionChange(Array.from(this.state.selectedRows));
        }
    }
    
    handleSelectAll(isChecked) {
        const dataToSelect = this.getPaginatedData(); // Solo seleccionar las visibles en la página actual
        dataToSelect.forEach(row => {
            const rowId = row[this.getPrimaryKey()];
            if (isChecked) {
                this.state.selectedRows.add(rowId);
            } else {
                this.state.selectedRows.delete(rowId);
            }
        });
        this.updateSelectionUI();
        if (this.config.onSelectionChange) {
            this.config.onSelectionChange(Array.from(this.state.selectedRows));
        }
    }
    
    updateSelectionUI() {
        // Actualizar checkboxes individuales
        this.state.tableElement.querySelectorAll('.row-selector').forEach(cb => {
            cb.checked = this.state.selectedRows.has(cb.dataset.rowId);
        });
        
        // Actualizar checkbox "select all"
        const selectAllCheckbox = this.state.tableElement.querySelector('.select-all-rows');
        if (selectAllCheckbox) {
            const visibleRows = this.getPaginatedData();
            const allVisibleSelected = visibleRows.length > 0 && visibleRows.every(row => this.state.selectedRows.has(row[this.getPrimaryKey()]));
            selectAllCheckbox.checked = allVisibleSelected;
            selectAllCheckbox.indeterminate = !allVisibleSelected && this.state.selectedRows.size > 0 && visibleRows.some(row => this.state.selectedRows.has(row[this.getPrimaryKey()]));
        }
    }

    /**
     * Cargar datos desde el servidor
     */
    async fetchData() {
        if (!this.config.dataUrl) return;
        this.state.isLoading = true;
        this.showLoading();

        try {
            const params = new URLSearchParams({
                page: this.state.currentPage,
                pageSize: this.config.pageSize,
                sortColumn: this.state.currentSortColumn || '',
                sortOrder: this.state.currentSortOrder || '',
                filter: this.state.currentFilter || ''
            });
            
            const response = await fetch(`${this.config.dataUrl}?${params.toString()}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const result = await response.json();
            
            this.state.data = result.data;
            this.state.totalRows = result.totalRows;
            this.render();
            
        } catch (error) {
            console.error('Error fetching data:', error);
            this.handleError(error);
        } finally {
            this.state.isLoading = false;
            this.hideLoading();
        }
    }

    /**
     * Utilidades
     */
    getNestedValue(obj, path) {
        return path.split('.').reduce((acc, part) => acc && acc[part], obj);
    }

    getPrimaryKey() {
        // Asumir que la primera columna es la clave primaria si no se especifica
        return this.config.primaryKey || (this.config.columns.length > 0 ? this.config.columns[0].key : 'id');
    }
    
    debounce(func, delay) {
        let timeout;
        return (...args) => {
            clearTimeout(timeout);
            timeout = setTimeout(() => func.apply(this, args), delay);
        };
    }

    showLoading() {
        const existingLoader = this.element.querySelector('.table-loader');
        if (existingLoader) existingLoader.remove();

        const loader = document.createElement('div');
        loader.className = 'table-loader';
        loader.innerHTML = `<div class="spinner-border spinner-border-sm" role="status"><span class="visually-hidden">${this.config.loadingMessage}</span></div> ${this.config.loadingMessage}`;
        this.element.insertBefore(loader, this.element.firstChild);
    }

    hideLoading() {
        const loader = this.element.querySelector('.table-loader');
        if (loader) loader.remove();
    }

    handleError(error) {
        // Mostrar error en la tabla
        if (this.state.tableElement) {
            let tbody = this.state.tableElement.querySelector('tbody');
            if (!tbody) {
                tbody = document.createElement('tbody');
                this.state.tableElement.appendChild(tbody);
            }
            tbody.innerHTML = `<tr><td colspan="100%" class="text-center text-danger">Error: ${error.message}</td></tr>`;
        }
    }

    /**
     * API Pública
     */
    refresh() {
        if (this.config.serverSide) {
            this.fetchData();
        } else {
            this.render();
        }
    }
    
    getSelectedRowsData() {
        const pk = this.getPrimaryKey();
        return this.state.data.filter(row => this.state.selectedRows.has(row[pk]));
    }

    destroy() {
        // Limpiar event listeners, timeouts, etc.
        this.element.innerHTML = '';
        console.log('📊 EcoTableManager destroyed');
    }
}

// CSS básico (idealmente en un archivo .css separado)
const tableManagerCSS = `
    .eco-table-manager.responsive { overflow-x: auto; }
    .eco-table-manager .table-controls-top { display: flex; justify-content: space-between; margin-bottom: 1rem; }
    .eco-table-manager .table-filter input { max-width: 300px; }
    .eco-table-manager th.sortable { cursor: pointer; }
    .eco-table-manager th.sortable:hover { background-color: #f8f9fa; }
    .eco-table-manager th.sorted-asc::after { content: " ▲"; }
    .eco-table-manager th.sorted-desc::after { content: " ▼"; }
    .eco-table-manager .table-pagination { margin-top: 1rem; }
    .eco-table-manager .table-loader { padding: 1rem; text-align: center; color: #6c757d; }
    .eco-table-manager.theme-dark { background-color: #212529; color: #fff; }
    .eco-table-manager.theme-dark .table { color: #fff; }
    .eco-table-manager.theme-dark .table-striped tbody tr:nth-of-type(odd) { background-color: rgba(255,255,255,.05); }
    .eco-table-manager.theme-dark .page-link { background-color: #343a40; border-color: #454d55; color: #fff; }
    .eco-table-manager.theme-dark .page-item.disabled .page-link { background-color: #212529; border-color: #343a40; color: #6c757d; }
    .eco-table-manager.theme-dark .page-item.active .page-link { background-color: #0d6efd; border-color: #0d6efd; }
`;

if (!document.getElementById('eco-table-manager-styles')) {
    const style = document.createElement('style');
    style.id = 'eco-table-manager-styles';
    style.textContent = tableManagerCSS;
    document.head.appendChild(style);
}

window.EcoTableManager = EcoTableManager;
export default EcoTableManager;
