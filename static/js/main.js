// General utility functions for the classroom application

function toggleModal(modalID) {
    const modal = document.getElementById(modalID);
    if (modal) {
        modal.classList.toggle('hidden');
    }
}

// Role selection toggle for Registration Page
function toggleSchoolFields() {
    const role = document.getElementById('role-select');
    const nameField = document.getElementById('school-name-field');
    const codeField = document.getElementById('school-code-field');
    
    if(!role || !nameField || !codeField) return;

    if(role.value === 'principal') {
        nameField.classList.remove('hidden');
        codeField.classList.add('hidden');
    } else {
        nameField.classList.add('hidden');
        codeField.classList.remove('hidden');
    }
}