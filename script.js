const $=s=>document.querySelector(s);
const $$=s=>document.querySelectorAll(s);

/* Independent cart open/close delegation */
document.addEventListener('click', event => {
  const overlay = document.getElementById('cartOverlay');
  if (!overlay) return;

  if (event.target.closest('.cart')) {
    event.preventDefault();
    overlay.classList.add('open');
    document.body.classList.add('cart-open');
  } else if (
    event.target.closest('#closeCart') ||
    event.target === overlay
  ) {
    overlay.classList.remove('open');
    document.body.classList.remove('cart-open');
  }
});


const menu=$('#mobileMenu');
$('#menuBtn').onclick=()=>menu.classList.add('open');
$('#closeMenu').onclick=()=>menu.classList.remove('open');
$$('.mobile-menu a').forEach(a=>a.onclick=()=>menu.classList.remove('open'));

let slide = 0;
const slides = [...document.querySelectorAll('.hero-slide')];
const dots = $('#heroDots');
const heroTrack = $('#heroTrack');

function showSlide(i) {
  if (!slides.length) return;
  slide = (i + slides.length) % slides.length;
  slides.forEach((item, n) => item.classList.toggle('active', n === slide));
  [...dots.children].forEach((item, n) => item.classList.toggle('active', n === slide));
}

slides.forEach((_, i) => {
  const b = document.createElement('button');
  b.type = 'button';
  b.setAttribute('aria-label', 'اسلاید ' + (i + 1));
  b.onclick = () => {
    showSlide(i);
    restartHeroTimer();
  };
  dots.appendChild(b);
});

showSlide(0);

let heroTimer;
function restartHeroTimer() {
  clearInterval(heroTimer);
  if (slides.length > 1) {
    heroTimer = setInterval(() => showSlide(slide + 1), 5000);
  }
}
restartHeroTimer();

let swipeStartX = 0;
let swipeStartY = 0;
let isSwiping = false;

heroTrack.addEventListener('pointerdown', e => {
  swipeStartX = e.clientX;
  swipeStartY = e.clientY;
  isSwiping = true;
  heroTrack.setPointerCapture(e.pointerId);
});

heroTrack.addEventListener('pointerup', e => {
  if (!isSwiping) return;
  isSwiping = false;

  const dx = e.clientX - swipeStartX;
  const dy = e.clientY - swipeStartY;

  if (Math.abs(dx) > 40 && Math.abs(dx) > Math.abs(dy)) {
    showSlide(slide + (dx < 0 ? 1 : -1));
    restartHeroTimer();
  }
});

heroTrack.addEventListener('pointercancel', () => {
  isSwiping = false;
});

$$('[data-scroll]').forEach(b=>b.onclick=()=>{
 const el=document.getElementById(b.dataset.scroll);
 el.scrollBy({left:Number(b.dataset.dir)*el.clientWidth*.8,behavior:'smooth'});
});

$$('.product-track,.blog-track').forEach(el=>{
 let down=false,startX=0,scroll=0;
 el.addEventListener('pointerdown',e=>{
  down=true;
  startX=e.clientX;
  scroll=el.scrollLeft;
 });
 el.addEventListener('pointerup',()=>down=false);
 el.addEventListener('pointercancel',()=>down=false);
 el.addEventListener('pointermove',e=>{
  if(!down)return;
  el.scrollLeft=scroll-(e.clientX-startX);
 });
});

/* Persistent shopping cart */
const CART_KEY = 'drBorudatCart';
let cart = [];
try {
  const saved = JSON.parse(localStorage.getItem(CART_KEY) || '[]');
  if (Array.isArray(saved)) cart = saved.filter(x =>
    x && typeof x.name === 'string' &&
    Number.isFinite(Number(x.price)) &&
    Number.isInteger(Number(x.qty)) &&
    Number(x.price) > 0 && Number(x.qty) > 0
  ).map(x => ({name:x.name, price:Number(x.price), qty:Number(x.qty)}));
} catch (_) { cart = []; }

const normalizeDigits = value => String(value)
  .replace(/[۰-۹]/g, d => '۰۱۲۳۴۵۶۷۸۹'.indexOf(d))
  .replace(/[٠-٩]/g, d => '٠١٢٣٤٥٦٧٨٩'.indexOf(d));

const readPrice = value => Number(normalizeDigits(value).replace(/[^\d]/g, '')) || 0;
const formatMoney = value => Math.round(value).toLocaleString('fa-IR') + ' تومان';

function saveCart() {
  localStorage.setItem(CART_KEY, JSON.stringify(cart));
}

function renderCart() {
  const count = cart.reduce((sum, item) => sum + item.qty, 0);
  $('#cartCount').textContent = count.toLocaleString('fa-IR');

  $('#cartItems').innerHTML = cart.map((item, index) => `
    <article class="cart-row">
      <div>
        <h3>${item.name}</h3>
        <div class="cart-price">${formatMoney(item.price)} برای هر عدد</div>
        <div class="cart-line-total">${formatMoney(item.price * item.qty)}</div>
      </div>
      <div class="cart-controls">
        <button type="button" data-cart-action="plus" data-index="${index}">+</button>
        <b>${item.qty.toLocaleString('fa-IR')}</b>
        <button type="button" data-cart-action="minus" data-index="${index}">−</button>
        <button type="button" class="cart-remove" data-cart-action="remove" data-index="${index}" aria-label="حذف">×</button>
      </div>
    </article>
  `).join('');

  $('#cartEmpty').classList.toggle('show', cart.length === 0);
  $('#cartFooter').style.display = cart.length ? 'block' : 'none';
  $('#cartTotal').textContent = formatMoney(
    cart.reduce((sum, item) => sum + item.price * item.qty, 0)
  );
}

function openCart() {
  $('#cartOverlay').classList.add('open');
  document.body.classList.add('cart-open');
}

function closeCart() {
  $('#cartOverlay').classList.remove('open');
  document.body.classList.remove('cart-open');
}

$$('.add-cart').forEach(button => {
  button.addEventListener('click', () => {
    const card = button.closest('.product-card');
    if (!card) return;

    const name = card.querySelector('h3')?.textContent.trim();
    const price = readPrice(card.querySelector('.price')?.textContent || '');

    if (!name || !price) {
      alert('نام یا قیمت این محصول مشخص نیست.');
      return;
    }

    const existing = cart.find(item => item.name === name && item.price === price);
    if (existing) existing.qty += 1;
    else cart.push({name, price, qty:1});

    saveCart();
    renderCart();
    openCart();
  });
});

$('#cartItems').addEventListener('click', event => {
  const button = event.target.closest('[data-cart-action]');
  if (!button) return;

  const index = Number(button.dataset.index);
  const item = cart[index];
  if (!item) return;

  if (button.dataset.cartAction === 'plus') item.qty += 1;
  if (button.dataset.cartAction === 'minus') item.qty -= 1;
  if (button.dataset.cartAction === 'remove' || item.qty <= 0) {
    cart.splice(index, 1);
  }

  saveCart();
  renderCart();
});

$('.cart').addEventListener('click', openCart);

$$('.bottom-nav a').forEach(link => {
  if (link.textContent.includes('سبد خرید')) {
    link.addEventListener('click', event => {
      event.preventDefault();
      openCart();
    });
  }
});

$('#closeCart').addEventListener('click', closeCart);
$('#cartOverlay').addEventListener('click', event => {
  if (event.target === $('#cartOverlay')) closeCart();
});
document.addEventListener('keydown', event => {
  if (event.key === 'Escape') closeCart();
});

$('#checkoutBtn').addEventListener('click', () => {
  alert('فرم مشخصات و ثبت سفارش در مرحله بعد اضافه می‌شود.');
});

renderCart();

$$('.favorite').forEach(b=>b.onclick=()=>{
 b.classList.toggle('selected');
 b.innerHTML=b.classList.contains('selected')
 ?'<i class="fa-solid fa-heart"></i>'
 :'<i class="fa-regular fa-heart"></i>';
});

$$('.tabs button').forEach(b=>b.onclick=()=>{
 $$('.tabs button').forEach(x=>x.classList.remove('active'));
 b.classList.add('active');
});

$('#filterBtn').onclick=()=>{
 const category=$('#categoryFilter').value;
 const stock=$('#stockFilter').value;
 alert('فیلتر انتخاب شد: '+(category||'همه دسته‌ها')+' | '+(stock||'همه وضعیت‌ها'));
};

$('#backTop').onclick=()=>window.scrollTo({top:0,behavior:'smooth'});
