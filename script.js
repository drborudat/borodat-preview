const $=s=>document.querySelector(s);
const $$=s=>document.querySelectorAll(s);

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

let count=0;
$$('.add-cart').forEach(b=>b.onclick=()=>{
 count++;
 $('#cartCount').textContent=count.toLocaleString('fa-IR');
});

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
