const toRegister = document.getElementById('toRegister');
const toLogin = document.getElementById('toLogin');
const loginForm = document.getElementById('loginForm');
const registerForm = document.getElementById('registerForm');

toRegister.addEventListener('click', (e) => {
  e.preventDefault();
  loginForm.classList.remove('active');
  registerForm.classList.add('active');
});

toLogin.addEventListener('click', (e) => {
  e.preventDefault();
  registerForm.classList.remove('active');
  loginForm.classList.add('active');
});
