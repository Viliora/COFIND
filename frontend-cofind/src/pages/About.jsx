import React, { useEffect, useState } from 'react';
import anggiPerwitasariPhoto from '../assets/team/anggi-perwitasari.png';
import hengkyAnraPhoto from '../assets/team/hengky-anra.png';
import mohammadAnandaFulviPhoto from '../assets/team/mohammad-ananda-fulvi.png';

const TEAM = [
  {
    name: 'Mohammad Ananda Fulvi',
    title: 'Pengembang',
    bio: 'Merancang dan mengembangkan Cofind sebagai platform rekomendasi coffee shop berbasis ulasan untuk Pontianak.',
    initials: 'MA',
    photo: mohammadAnandaFulviPhoto,
  },
  {
    name: 'Anggi Perwitasari',
    title: 'S. T., M. T.',
    bio: 'Dosen pembimbing yang memberikan arahan akademik dalam perancangan dan pengembangan Cofind.',
    initials: 'AP',
    photo: anggiPerwitasariPhoto,
  },
  {
    name: 'H. Hengky Anra',
    title: 'S. T., M. Kom.',
    bio: 'Dosen pembimbing yang memberikan bimbingan teknis dan akademik selama pengerjaan proyek Cofind.',
    initials: 'HA',
    photo: hengkyAnraPhoto,
  },
];

export default function About() {
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    document.title = 'Tentang - Cofind';
    const t = requestAnimationFrame(() => setMounted(true));
    return () => {
      cancelAnimationFrame(t);
      document.title = 'Cofind';
    };
  }, []);

  return (
    <div className="min-h-screen bg-cofind-background py-6 sm:py-10 px-3 sm:px-4 md:px-6 lg:px-8">
      <div className="mx-auto max-w-cofind">
        <header
          className={`text-center transition-opacity duration-500 ${
            mounted ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <h1 className="px-2 font-display text-2xl font-bold text-cofind-ink sm:text-3xl md:text-4xl">
            Cofind
          </h1>
        </header>

        <div
          className={`mt-8 space-y-10 transition-opacity duration-500 sm:mt-10 sm:space-y-12 ${
            mounted ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <article className="rounded-panel border border-cofind-rule bg-cofind-surface p-5 shadow-cofind-sm sm:p-8">
            <div className="space-y-5 font-sans text-sm leading-relaxed text-cofind-ink sm:text-base">
              <p>
                Cofind adalah aplikasi web yang membantu Anda menemukan dan menjelajahi coffee shop di Pontianak. Temukan berbagai tempat melalui katalog dan peta interaktif, lalu dapatkan rekomendasi yang mempertimbangkan lebih dari sekadar angka rating. Cofind memadukan informasi tempat dengan pengalaman yang dibagikan pengunjung melalui ulasan, sehingga Anda dapat menemukan coffee shop yang lebih sesuai dengan kebutuhan dan aktivitas Anda.
              </p>

              <p>
                Dibangun dari gagasan bahwa coffee shop terbaik bukan selalu yang memiliki rating tertinggi, Cofind membantu menyaring berbagai informasi dari ulasan dan preferensi pengguna untuk menemukan tempat yang benar-benar relevan. Baik untuk belajar, bekerja, nge-game, pertemuan, maupun berkumpul bersama keluarga. Rekomendasi Cofind dirancang untuk membantu Anda menemukan tempat yang sesuai dengan konteks dan kebutuhan. Setiap rekomendasi juga dilengkapi dengan kutipan ulasan yang relevan, memberikan gambaran nyata mengenai pengalaman pengunjung sebelum Anda berkunjung.
              </p>

              <p>
                Cofind dapat diakses melalui peramban dan terbuka bagi siapa saja. Pengunjung tanpa akun dapat menjelajahi katalog coffee shop, melihat lokasi melalui peta, serta memperoleh informasi mengenai berbagai tempat. Dengan membuat akun, pengguna dapat menikmati pengalaman yang lebih personal, termasuk mendapatkan rekomendasi berdasarkan preferensi, menulis ulasan, menyimpan coffee shop favorit, dan membuat daftar tempat yang ingin dikunjungi. Penggunaan Cofind tidak memerlukan biaya apa pun, dan selalu tersedia untuk semua pengguna.
              </p>

              <p>
                Cofind hadir untuk siapa saja yang ingin menemukan coffee shop di Pontianak dengan cara yang lebih bermakna. Mulai dari mahasiswa dan pekerja hingga keluarga, komunitas, dan para penikmat kopi yang selalu mencari tempat baru untuk dikunjungi.
              </p>

              <p>
                *Note: cofind is solely a coffee shop recommendation website and does not sell coffee.
              </p>
            </div>
          </article>

          <section>
            <h2 className="font-display text-xl font-bold text-cofind-ink sm:text-2xl">Cofind Team</h2>
            <div className="mt-5 grid grid-cols-1 gap-4 sm:grid-cols-2 sm:gap-5 xl:grid-cols-3">
              {TEAM.map((member) => (
                <article
                  key={member.name}
                  className="rounded-panel border border-cofind-rule bg-cofind-surface p-5 shadow-cofind-sm"
                >
                  <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full border border-cofind-rule bg-cofind-paper text-lg font-semibold text-cofind-ink">
                    {member.photo ? (
                      <img src={member.photo} alt={member.name} className="h-full w-full object-cover" />
                    ) : (
                      member.initials
                    )}
                  </div>
                  <h3 className="mt-4 font-display text-lg font-semibold text-cofind-ink">{member.name}</h3>
                  <p className="mt-0.5 text-sm font-medium text-cofind-secondary">{member.title}</p>
                  <p className="mt-2 text-sm leading-relaxed text-cofind-muted">{member.bio}</p>
                </article>
              ))}
            </div>
          </section>
        </div>

        <footer
          className={`mt-12 text-center font-sans text-xs text-cofind-muted transition-opacity duration-500 sm:mt-14 ${
            mounted ? 'opacity-100' : 'opacity-0'
          }`}
        >
          <p>Terima kasih telah menggunakan Cofind — selamat menjelajahi coffee shop Pontianak.</p>
        </footer>
      </div>
    </div>
  );
}